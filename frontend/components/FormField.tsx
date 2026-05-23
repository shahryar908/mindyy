type Props = {
  id: string;
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  rightSlot?: React.ReactNode;
  autoComplete?: string;
  required?: boolean;
};

export function FormField({
  id,
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  rightSlot,
  autoComplete,
  required,
}: Props) {
  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-end justify-between">
        <label htmlFor={id} className="font-label text-secondary">
          {label}
        </label>
        {rightSlot}
      </div>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        autoComplete={autoComplete}
        required={required}
        className="input-underlined py-3 text-base text-primary placeholder:text-outline-variant"
      />
    </div>
  );
}
