import React, { DragEvent, ReactNode, useState } from "react";

type Props = {
  disabled?: boolean;
  children: ReactNode;
  onFilesDropped: (files: File[]) => void;
};

export function FileUpload({ disabled = false, children, onFilesDropped }: Props): JSX.Element {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrag = (event: DragEvent<HTMLDivElement>, dragging: boolean) => {
    event.preventDefault();
    event.stopPropagation();
    if (!disabled) {
      setIsDragging(dragging);
    }
  };

  return (
    <div
      className="chat-drop-surface"
      onDragEnter={(event) => handleDrag(event, true)}
      onDragOver={(event) => handleDrag(event, true)}
      onDragLeave={(event) => handleDrag(event, false)}
      onDrop={(event) => {
        handleDrag(event, false);
        const files = Array.from(event.dataTransfer.files ?? []);
        if (!disabled && files.length) {
          onFilesDropped(files);
        }
      }}
    >
      {children}
      {isDragging ? <div className="drop-overlay">Drop tax documents to upload and index</div> : null}
    </div>
  );
}
