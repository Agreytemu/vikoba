import { FC, useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "react-toastify";

import { SYSTEM_NAME, LOGO_URL } from "@/lib/system";
import { Auth } from "@/contexts/AuthContext";
import { useAcceptInvite } from "@/hooks/api/groups";
import { getApiErrorMessage } from "@/lib/utils";
import Button from "@/components/Button";
import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";

/**
 * Landing used by emailed group invitations (/groups/invite/:token). Visitors
 * are prompted to log in (or register) with the invited email; signed-in
 * members accept the invitation automatically.
 */
const InviteAccept: FC = () => {
  const { token } = useParams();
  const navigate = useNavigate();
  const { isAuthenticated } = Auth();
  const acceptInvite = useAcceptInvite();

  const [error, setError] = useState("");
  const [tried, setTried] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || !token) return;
    if (tried) return;
    setTried(true);
    setError("");
    acceptInvite.mutate(token, {
      onSuccess: (group) => {
        toast.success(`You joined ${group.name}.`, { autoClose: 3000 });
        navigate("/groups", { replace: true });
      },
      onError: (err) => {
        setError(getApiErrorMessage(err, "Could not accept this invitation."));
      },
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isAuthenticated, token]);

  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-paper px-4 py-10 text-ink dark:bg-[#0d1117] dark:text-slate-100">
      <div className="w-full max-w-md rounded-3xl border border-slate-200 bg-white p-8 text-center shadow-card dark:border-slate-800 dark:bg-slate-900">
        <img
          src={LOGO_URL}
          alt={`${SYSTEM_NAME} logo`}
          className="mx-auto h-14 w-14 rounded-xl bg-blue-800/5 p-1"
        />
        <h1 className="mt-4 font-display text-2xl font-semibold">You're invited!</h1>

        {!isAuthenticated ? (
          <>
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">
              Sign in to accept this group invitation. Use the same email address
              the group leader invited.
            </p>
            <div className="mt-6 space-y-3">
              <Button
                text="Log in to accept"
                type="button"
                variant="primary"
                className="w-full"
                onClick={() =>
                  navigate("/login", {
                    replace: true,
                    state: { from: window.location.pathname },
                  })
                }
              />
              <p className="text-sm text-slate-500 dark:text-slate-400">
                No account yet?{" "}
                <Link
                  className="font-medium text-blue-700 hover:underline dark:text-blue-300"
                  to="/register"
                  state={{ from: window.location.pathname }}
                >
                  Register
                </Link>
              </p>
            </div>
          </>
        ) : acceptInvite.isPending ? (
          <div className="flex justify-center py-10">
            <Spinner />
          </div>
        ) : error ? (
          <div className="mt-6">
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-50 text-red-600 dark:bg-red-950/50 dark:text-red-400">
              <LucideIcon name="CircleAlert" size={24} />
            </span>
            <p className="mt-3 text-sm text-slate-600 dark:text-slate-300">{error}</p>
            <Button
              text="Back to my groups"
              type="button"
              variant="secondary"
              className="mt-5 w-full"
              onClick={() => navigate("/groups")}
            />
          </div>
        ) : (
          <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
            Processing your invitation…
          </p>
        )}
      </div>
    </div>
  );
};

export default InviteAccept;