import { FC } from "react";
import { useNavigate } from "react-router-dom";
import LucideIcon from "@/components/LucideIcon";
import Modal from "@/components/ui/Modal";
import { Button } from "@/components/ui/button";

interface VerificationGateProps {
  open: boolean;
  onClose: () => void;
  message?: string;
}

/**
 * Modal shown to unverified members when they try a verified-only feature
 * (create groups, buy hisa, invite others). Sends them to complete their
 * onboarding in their profile.
 */
const VerificationGate: FC<VerificationGateProps> = ({
  open,
  onClose,
  message = "Finish your verification to unlock this feature. You need to confirm your phone, add a next of kin and upload your ID, passport photo and signature, then staff approve them.",
}) => {
  const navigate = useNavigate();

  return (
    <Modal isOpen={open} onClose={onClose} title="Verification required">
      <div className="flex flex-col items-center py-2 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-950/50 dark:text-emerald-400">
          <LucideIcon name="BadgeCheck" size={28} />
        </span>
        <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{message}</p>
        <div className="mt-6 flex w-full justify-end gap-x-2">
          <Button type="button" variant="outline" onClick={onClose}>
            Not now
          </Button>
          <Button
            type="button"
            onClick={() => {
              onClose();
              navigate("/profile", { replace: true });
            }}
          >
            Finish verification
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default VerificationGate;