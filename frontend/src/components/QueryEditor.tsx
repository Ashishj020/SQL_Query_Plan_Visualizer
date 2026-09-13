import Editor, { type OnMount } from "@monaco-editor/react";
import { useRef } from "react";

const THEME = "planlight";

export function QueryEditor({
  value,
  onChange,
  onSubmit,
}: {
  value: string;
  onChange: (sql: string) => void;
  onSubmit: () => void;
}) {
  const submitRef = useRef(onSubmit);
  submitRef.current = onSubmit;

  const handleMount: OnMount = (editor, monaco) => {
    monaco.editor.defineTheme(THEME, {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "keyword", foreground: "5EEAD4" },
        { token: "string", foreground: "86EFAC" },
        { token: "number", foreground: "FBBF24" },
        { token: "comment", foreground: "64748B" },
        { token: "operator", foreground: "818CF8" },
      ],
      colors: {
        "editor.background": "#070B14",
        "editor.foreground": "#F4F7FB",
        "editorLineNumber.foreground": "#475569",
        "editor.selectionBackground": "#134E4A80",
        "editorCursor.foreground": "#5EEAD4",
        "editor.lineHighlightBackground": "#0F172A80",
      },
    });
    monaco.editor.setTheme(THEME);
    editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.Enter, () => submitRef.current());
  };

  return (
    <div className="glass editor-well">
      <Editor
        height="100%"
        language="sql"
        value={value}
        onChange={(next) => onChange(next ?? "")}
        onMount={handleMount}
        options={{
          minimap: { enabled: false },
          fontFamily: "JetBrains Mono, ui-monospace, monospace",
          fontSize: 13,
          lineHeight: 21,
          padding: { top: 14, bottom: 14 },
          scrollBeyondLastLine: false,
          automaticLayout: true,
          renderLineHighlight: "line",
          overviewRulerLanes: 0,
          hideCursorInOverviewRuler: true,
          scrollbar: { verticalScrollbarSize: 8 },
        }}
      />
    </div>
  );
}
