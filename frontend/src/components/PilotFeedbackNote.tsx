import { AlertTriangle, ClipboardCheck } from "lucide-react";

type PilotFeedbackNoteProps = {
  title: string;
  items: string[];
  tone?: "blue" | "amber";
};

export function PilotFeedbackNote({ title, items, tone = "blue" }: PilotFeedbackNoteProps) {
  const toneClass = tone === "amber"
    ? "border-amber-200 bg-amber-50 text-amber-900"
    : "border-blue-100 bg-blue-50 text-blue-900";
  const iconClass = tone === "amber" ? "text-amber-600" : "text-blue-600";
  const Icon = tone === "amber" ? AlertTriangle : ClipboardCheck;

  return (
    <div className={`rounded-xl border px-4 py-3 ${toneClass}`}>
      <div className="flex items-start gap-3">
        <Icon className={`mt-0.5 shrink-0 ${iconClass}`} size={18} />
        <div>
          <p className="text-sm font-black">{title}</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {items.map((item) => (
              <span key={item} className="rounded-full bg-white/75 px-2.5 py-1 text-xs font-semibold shadow-sm">
                {item}
              </span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
