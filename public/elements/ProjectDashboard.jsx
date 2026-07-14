import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { FileText, FolderOpen, FolderPlus, Upload } from "lucide-react";

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ProjectDashboard() {
  const [showForm, setShowForm] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDescription, setNewDescription] = useState("");

  const submitNewProject = () => {
    if (!newName.trim()) return;
    callAction({
      name: "create_project",
      payload: { name: newName.trim(), description: newDescription.trim() },
    });
    setShowForm(false);
    setNewName("");
    setNewDescription("");
  };

  return (
    <Card className="max-w-md border-purple-300 dark:border-purple-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FolderOpen className="h-5 w-5 text-purple-500" />
          {props.name ? `Project: ${props.name}` : "No project selected"}
        </CardTitle>
        <CardDescription>
          {props.name
            ? props.description || "No description yet."
            : "Pick a project from the profile dropdown, or create a new one."}
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        {props.name && (
          <div>
            <p className="text-sm font-medium mb-1">
              Shared files ({props.files.length})
            </p>
            {props.files.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                No files attached to this project yet.
              </p>
            ) : (
              <ul className="space-y-1">
                {props.files.map((file) => (
                  <li
                    key={file.name}
                    className="flex items-center gap-2 text-sm"
                  >
                    <FileText className="h-4 w-4 text-muted-foreground" />
                    <span className="truncate">{file.name}</span>
                    <span className="ml-auto text-muted-foreground">
                      {formatSize(file.size)}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
        {showForm && (
          <div className="space-y-2 rounded-md border p-3">
            <Input
              placeholder="Project name (e.g. Dryback)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
            />
            <Textarea
              placeholder="Business context: what the client does, location, size…"
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={submitNewProject}>
                Create
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setShowForm(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </CardContent>
      <CardFooter className="flex gap-2">
        {props.name && (
          <Button
            size="sm"
            onClick={() => callAction({ name: "add_project_files", payload: {} })}
          >
            <Upload className="h-4 w-4 mr-1" /> Add files
          </Button>
        )}
        {!showForm && (
          <Button size="sm" variant="outline" onClick={() => setShowForm(true)}>
            <FolderPlus className="h-4 w-4 mr-1" /> New project
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
