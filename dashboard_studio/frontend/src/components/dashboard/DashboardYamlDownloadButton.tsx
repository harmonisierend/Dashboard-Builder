interface DashboardYamlDownloadButtonProps {
  yaml: string;
}

export function DashboardYamlDownloadButton({ yaml }: DashboardYamlDownloadButtonProps) {
  function handleDownload() {
    const blob = new Blob([yaml], { type: "application/x-yaml" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "dashboard.yaml";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <button
      type="button"
      onClick={handleDownload}
      className="rounded border border-gray-300 px-3 py-1 text-sm hover:bg-gray-50"
    >
      dashboard.yaml herunterladen
    </button>
  );
}
