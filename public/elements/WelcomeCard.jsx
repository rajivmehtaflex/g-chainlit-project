import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Sparkles } from "lucide-react";

export default function WelcomeCard() {
  return (
    <Card className="max-w-md border-purple-300 dark:border-purple-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-purple-500" />
          {props.title}
        </CardTitle>
        <CardDescription>{props.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <Button onClick={() => sendUserMessage("Hello!")}>Say hello</Button>
      </CardContent>
    </Card>
  );
}
