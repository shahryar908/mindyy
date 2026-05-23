/**
 * Minimal SSE frame parser. Yields { event, data } objects as full frames arrive.
 * Frames are separated by a blank line. Each frame has lines like:
 *   event: <name>
 *   data: <text>
 */

export type SseFrame = { event: string; data: string };

export async function* parseSseStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
): AsyncGenerator<SseFrame> {
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) {
      if (buffer.trim()) {
        const frame = parseFrame(buffer);
        if (frame) yield frame;
      }
      return;
    }
    buffer += decoder.decode(value, { stream: true });

    // Split on \n\n; the last chunk may be partial.
    let idx;
    while ((idx = buffer.indexOf("\n\n")) !== -1) {
      const raw = buffer.slice(0, idx);
      buffer = buffer.slice(idx + 2);
      const frame = parseFrame(raw);
      if (frame) yield frame;
    }
  }
}

function parseFrame(raw: string): SseFrame | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of raw.split("\n")) {
    if (!line || line.startsWith(":")) continue;
    const colon = line.indexOf(":");
    if (colon === -1) continue;
    const field = line.slice(0, colon).trim();
    // Per SSE spec, an optional single space after colon is consumed.
    const value = line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") event = value;
    else if (field === "data") dataLines.push(value);
  }
  if (dataLines.length === 0 && event === "message") return null;
  return { event, data: dataLines.join("\n") };
}
