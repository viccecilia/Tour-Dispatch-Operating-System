import { Card, CardContent } from "@/components/ui/card";

export function PlaceholderPage({ title, description }: { title: string; description: string }) {
  return (
    <Card>
      <CardContent>
        <p className="text-lg font-semibold text-slate-950">{title}</p>
        <p className="mt-2 text-sm text-slate-500">{description}</p>
      </CardContent>
    </Card>
  );
}
