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
import {
  Check,
  FileText,
  FolderOpen,
  Pencil,
  Trash2,
  Upload,
  X,
} from "lucide-react";

function formatSize(bytes) {
  if (!bytes && bytes !== 0) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileRow({ file }) {
  const [editing, setEditing] = useState(false);
  const [draftName, setDraftName] = useState(file.name);

  const saveRename = () => {
    const trimmed = draftName.trim();
    if (!trimmed || trimmed === file.name) {
      setEditing(false);
      return;
    }
    callAction({
      name: "rename_project_file",
      payload: { file_id: file.id, new_name: trimmed },
    });
    setEditing(false);
  };

  const deleteFile = () => {
    if (!window.confirm(`Delete "${file.name}"? This cannot be undone.`)) return;
    callAction({ name: "delete_project_file", payload: { file_id: file.id } });
  };

  if (editing) {
    return (
      <li className="flex items-center gap-2 text-sm">
        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
        <Input
          className="h-7"
          value={draftName}
          onChange={(e) => setDraftName(e.target.value)}
          autoFocus
        />
        <Button size="icon" variant="ghost" className="h-7 w-7" onClick={saveRename}>
          <Check className="h-4 w-4" />
        </Button>
        <Button
          size="icon"
          variant="ghost"
          className="h-7 w-7"
          onClick={() => {
            setDraftName(file.name);
            setEditing(false);
          }}
        >
          <X className="h-4 w-4" />
        </Button>
      </li>
    );
  }

  return (
    <li className="flex items-center gap-2 text-sm">
      <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
      <span className="truncate">{file.name}</span>
      <span className="ml-auto text-muted-foreground">{formatSize(file.size)}</span>
      <Button
        size="icon"
        variant="ghost"
        className="h-7 w-7"
        onClick={() => {
          setDraftName(file.name);
          setEditing(true);
        }}
      >
        <Pencil className="h-3.5 w-3.5" />
      </Button>
      <Button size="icon" variant="ghost" className="h-7 w-7" onClick={deleteFile}>
        <Trash2 className="h-3.5 w-3.5" />
      </Button>
    </li>
  );
}

export default function ProjectDashboard() {
  const [editingDescription, setEditingDescription] = useState(false);
  const [descriptionDraft, setDescriptionDraft] = useState(props.description || "");
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [deleteConfirmName, setDeleteConfirmName] = useState("");

  const saveDescription = () => {
    callAction({
      name: "update_project_description",
      payload: { description: descriptionDraft.trim() },
    });
    setEditingDescription(false);
  };

  const confirmDelete = () => {
    callAction({
      name: "delete_project",
      payload: { confirm_name: deleteConfirmName.trim() },
    });
    setConfirmingDelete(false);
    setDeleteConfirmName("");
  };

  return (
    <Card className="max-w-md border-purple-300 dark:border-purple-800">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <FolderOpen className="h-5 w-5 text-purple-500" />
          {props.name ? `Project: ${props.name}` : "No project selected"}
        </CardTitle>
        {props.name && !editingDescription && (
          <div className="flex items-start gap-2">
            <CardDescription className="flex-1">
              {props.description || "No description yet."}
            </CardDescription>
            <Button
              size="icon"
              variant="ghost"
              className="h-6 w-6 shrink-0"
              onClick={() => {
                setDescriptionDraft(props.description || "");
                setEditingDescription(true);
              }}
            >
              <Pencil className="h-3.5 w-3.5" />
            </Button>
          </div>
        )}
        {!props.name && (
          <CardDescription>
            Pick a project from the profile dropdown, or create a new one from the
            settings panel (gear icon).
          </CardDescription>
        )}
        {props.name && editingDescription && (
          <div className="space-y-2">
            <Textarea
              value={descriptionDraft}
              onChange={(e) => setDescriptionDraft(e.target.value)}
              placeholder="Business context: what the client does, location, size…"
            />
            <div className="flex gap-2">
              <Button size="sm" onClick={saveDescription}>
                Save
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={() => setEditingDescription(false)}
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
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
                  <FileRow key={file.id} file={file} />
                ))}
              </ul>
            )}
          </div>
        )}
        {props.name && (
          <div className="rounded-md border border-destructive/30 p-3 space-y-2">
            <p className="text-sm font-medium text-destructive">Danger zone</p>
            {!confirmingDelete ? (
              <Button
                size="sm"
                variant="destructive"
                onClick={() => setConfirmingDelete(true)}
              >
                <Trash2 className="h-4 w-4 mr-1" /> Delete project
              </Button>
            ) : (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  This deletes <strong>{props.name}</strong> and every thread tagged
                  with it. Type the project name to confirm.
                </p>
                <Input
                  value={deleteConfirmName}
                  onChange={(e) => setDeleteConfirmName(e.target.value)}
                  placeholder={props.name}
                />
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="destructive"
                    disabled={deleteConfirmName.trim() !== props.name}
                    onClick={confirmDelete}
                  >
                    Confirm delete
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      setConfirmingDelete(false);
                      setDeleteConfirmName("");
                    }}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </CardContent>
      <CardFooter>
        {props.name && (
          <Button
            size="sm"
            onClick={() => callAction({ name: "add_project_files", payload: {} })}
          >
            <Upload className="h-4 w-4 mr-1" /> Add files
          </Button>
        )}
      </CardFooter>
    </Card>
  );
}
