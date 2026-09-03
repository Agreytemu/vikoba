import { FC, useRef, useState } from "react";
import { toast } from "react-toastify";
import Modal from "@/components/ui/Modal";
import LucideIcon from "@/components/LucideIcon";
import PermissionSheet from "@/components/ui/PermissionSheet";

interface KycUploadButtonProps {
  uploaded?: boolean;
  uploading?: boolean;
  /** Takes the chosen camera/gallery file. */
  onUpload: (file: File) => void;
}

/**
 * "Upload" control for KYC documents. On phones this offers an explicit
 * "Take a photo" (camera permission) vs "Choose from gallery" choice instead
 * of silently opening a file picker, so the camera permission is requested
 * deliberately, right where it is needed.
 */
const KycUploadButton: FC<KycUploadButtonProps> = ({ uploaded, uploading, onUpload }) => {
  const [chooserOpen, setChooserOpen] = useState(false);
  const [cameraAskOpen, setCameraAskOpen] = useState(false);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const galleryInputRef = useRef<HTMLInputElement>(null);

  const fire = (input: HTMLInputElement | null) => {
    input?.click();
  };

  const MAX_KYC_BYTES = 10 * 1024 * 1024;

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) {
      e.target.value = "";
      return;
    }
    if (file.size > MAX_KYC_BYTES) {
      toast.error("File is too large — must be 10MB or less. Please compress the image or choose a smaller file.", { autoClose: 3500 });
      e.target.value = "";
      return;
    }
    onUpload(file);
    e.target.value = "";
  };

  return (
    <>
      <button
        type="button"
        disabled={uploading}
        onClick={() => setChooserOpen(true)}
        className={`mt-3 flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg border px-3 py-2 text-sm font-medium transition ${
          uploading
            ? "pointer-events-none opacity-50"
            : "border-blue-200 bg-blue-50 text-blue-700 hover:bg-blue-100 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300"
        }`}
      >
        <LucideIcon name="Upload" size={16} />
        {uploaded ? "Replace" : "Upload"}
      </button>

      <Modal isOpen={chooserOpen} onClose={() => setChooserOpen(false)} title="How do you want to upload?">
        <div className="space-y-3">
          <button
            type="button"
            onClick={() => {
              setChooserOpen(false);
              setCameraAskOpen(true);
            }}
            className="flex w-full items-center gap-3 rounded-xl border border-slate-200 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50/60 dark:border-slate-800 dark:hover:bg-blue-950/20"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
              <LucideIcon name="Camera" size={20} />
            </span>
            <span>
              <span className="block text-sm font-medium">Take a photo</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Uses your camera for a clear capture
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={() => {
              setChooserOpen(false);
              fire(galleryInputRef.current);
            }}
            className="flex w-full items-center gap-3 rounded-xl border border-slate-200 p-4 text-left transition hover:border-blue-300 hover:bg-blue-50/60 dark:border-slate-800 dark:hover:bg-blue-950/20"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
              <LucideIcon name="FolderOpen" size={20} />
            </span>
            <span>
              <span className="block text-sm font-medium">Choose from gallery</span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Pick a file already on this device
              </span>
            </span>
          </button>
        </div>
      </Modal>

      <PermissionSheet
        isOpen={cameraAskOpen}
        kind="camera"
        onClose={() => setCameraAskOpen(false)}
        onGranted={() => fire(cameraInputRef.current)}
      />

      {/* real inputs — hidden, triggered programmatically */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={handleFile}
      />
      <input
        ref={galleryInputRef}
        type="file"
        accept="image/*,.pdf"
        className="hidden"
        onChange={handleFile}
      />
    </>
  );
};

export default KycUploadButton;