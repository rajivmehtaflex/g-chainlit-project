import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

export default function ReloadPrompt() {
  return (
    <div className="flex items-center gap-3 rounded-md border border-purple-300 dark:border-purple-800 p-3 max-w-md">
      <p className="text-sm flex-1">{props.message}</p>
      <Button size="sm" onClick={() => window.location.reload()}>
        <RefreshCw className="h-4 w-4 mr-1" /> Reload now
      </Button>
    </div>
  );
}
