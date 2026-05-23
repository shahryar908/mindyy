import base64
import json
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from sqlmodel import Session, select

from db import get_session
from rate_limit import limiter
from auth.deps import get_current_user
from auth.tables import User

from photos.schemas import (
    FaceClusterRead,
    LabelClusterRequest,
    PhotoListResponse,
    PhotoRead,
    PhotoStatus,
    UploadResponse,
)
from photos.storage import (
    build_object_key,
    delete_object,
    generate_presigned_get_url,
    put_object,
)
from photos.tables import Face, FaceCluster, ItemStatus, ItemType, MemoryItem, PhotoMetadata


router = APIRouter(prefix="/photos", tags=["photos"])

ALLOWED_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/heic",
    "image/webp",
}
MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


async def enqueue_processing(memory_item_id: UUID) -> None:
    """In-process background task entrypoint. Tests patch this to a no-op."""
    from photos.processing.pipeline import run_photo_pipeline

    await run_photo_pipeline(memory_item_id)


def _photo_read_with_meta(item: MemoryItem, meta: Optional[PhotoMetadata]) -> PhotoRead:
    source_url = (
        generate_presigned_get_url(item.source_key)
        if item.status != ItemStatus.UPLOADING
        else None
    )
    thumbnail_url = (
        generate_presigned_get_url(item.thumbnail_key) if item.thumbnail_key else None
    )
    return PhotoRead(
        id=item.id,
        type=item.type,
        status=item.status,
        source_url=source_url,
        thumbnail_url=thumbnail_url,
        taken_at=item.taken_at,
        location=item.location,
        caption=meta.caption if meta else None,
        scenes=meta.scenes if meta else [],
        objects=meta.objects if meta else [],
        ocr_text=meta.ocr_text if meta else None,
        item_metadata=item.item_metadata or {},
        created_at=item.created_at,
    )


def _encode_cursor(item: MemoryItem) -> str:
    payload = {"ca": item.created_at.isoformat(), "id": str(item.id)}
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode()


def _decode_cursor(cursor: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())


# --- People endpoints come BEFORE /{photo_id} so the path doesn't collide ---


@router.get("/people", response_model=list[FaceClusterRead])
def list_people(
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    clusters = list(
        session.exec(
            select(FaceCluster)
            .where(FaceCluster.user_id == current_user.id)
            .order_by(FaceCluster.face_count.desc())
        )
    )

    out: list[FaceClusterRead] = []
    for c in clusters:
        # Pick the most recent ready photo that contains a face in this cluster.
        sample = session.exec(
            select(MemoryItem)
            .join(Face, Face.memory_item_id == MemoryItem.id)
            .where(
                Face.cluster_id == c.id,
                MemoryItem.status == ItemStatus.READY,
                MemoryItem.thumbnail_key.is_not(None),
            )
            .order_by(MemoryItem.created_at.desc())
            .limit(1)
        ).first()
        sample_url = (
            generate_presigned_get_url(sample.thumbnail_key)
            if sample is not None and sample.thumbnail_key
            else None
        )
        out.append(
            FaceClusterRead(
                id=c.id,
                label=c.label,
                face_count=c.face_count,
                sample_thumbnail_url=sample_url,
            )
        )
    return out


@router.patch("/people/{cluster_id}", response_model=FaceClusterRead)
def label_cluster(
    cluster_id: UUID,
    req: LabelClusterRequest,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cluster = session.get(FaceCluster, cluster_id)
    if cluster is None or cluster.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    cluster.label = req.label
    session.add(cluster)
    session.commit()
    session.refresh(cluster)
    return FaceClusterRead(
        id=cluster.id,
        label=cluster.label,
        face_count=cluster.face_count,
        sample_thumbnail_url=None,
    )


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("30/minute")
async def upload_photo(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unsupported content type {file.content_type}",
        )

    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="file too large (max 50 MB)",
        )

    filename = file.filename or "upload.jpg"
    s3_key = build_object_key(current_user.id, kind="photos", filename=filename)

    try:
        put_object(s3_key, file.file, file.content_type)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"storage upload failed: {exc.__class__.__name__}",
        )

    item = MemoryItem(
        user_id=current_user.id,
        type=ItemType.PHOTO,
        status=ItemStatus.UPLOADING,
        source_key=s3_key,
        item_metadata={
            "original_filename": filename,
            "content_type": file.content_type,
        },
    )
    session.add(item)
    session.commit()
    session.refresh(item)

    background_tasks.add_task(enqueue_processing, item.id)

    return UploadResponse(id=item.id, status=item.status)


@router.get("", response_model=PhotoListResponse)
def list_photos(
    limit: int = 50,
    cursor: Optional[str] = None,
    cluster_id: Optional[UUID] = None,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    limit = min(max(limit, 1), 100)

    stmt = (
        select(MemoryItem)
        .where(MemoryItem.user_id == current_user.id)
        .order_by(MemoryItem.created_at.desc(), MemoryItem.id.desc())
        .limit(limit + 1)
    )
    if cursor:
        c = _decode_cursor(cursor)
        cutoff = datetime.fromisoformat(c["ca"])
        stmt = stmt.where(MemoryItem.created_at < cutoff)

    if cluster_id is not None:
        # Verify the cluster belongs to this user before filtering — prevents
        # someone enumerating photos of another user's cluster by id.
        cluster = session.get(FaceCluster, cluster_id)
        if cluster is None or cluster.user_id != current_user.id:
            return PhotoListResponse(items=[], next_cursor=None)
        stmt = stmt.where(
            MemoryItem.id.in_(
                select(Face.memory_item_id)
                .where(Face.cluster_id == cluster_id)
                .distinct()
            )
        )

    items = list(session.exec(stmt))
    has_more = len(items) > limit
    items = items[:limit]

    next_cursor = _encode_cursor(items[-1]) if has_more and items else None

    out: list[PhotoRead] = []
    for it in items:
        meta = session.get(PhotoMetadata, it.id)
        out.append(_photo_read_with_meta(it, meta))

    return PhotoListResponse(items=out, next_cursor=next_cursor)


@router.get("/{photo_id}/status", response_model=PhotoStatus)
def photo_status(
    photo_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    item = session.get(MemoryItem, photo_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    return PhotoStatus(id=item.id, status=item.status)


@router.get("/{photo_id}", response_model=PhotoRead)
def get_photo(
    photo_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    item = session.get(MemoryItem, photo_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    meta = session.get(PhotoMetadata, item.id)
    return _photo_read_with_meta(item, meta)


@router.delete("/{photo_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_photo(
    photo_id: UUID,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    item = session.get(MemoryItem, photo_id)
    if item is None or item.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")

    delete_object(item.source_key)
    if item.thumbnail_key:
        delete_object(item.thumbnail_key)

    session.delete(item)
    session.commit()
    return None
