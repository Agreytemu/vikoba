import { Link } from "react-router-dom";
import LucideIcon from "@/components/LucideIcon";

export const BulkEmail = () => {
    return (
        <div className="mx-auto max-w-2xl rounded-lg border border-slate-200 bg-white p-10 text-center shadow-soft dark:border-slate-800 dark:bg-slate-900">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300">
                <LucideIcon name="Mail" size={28} />
            </div>
            <h1 className="mt-4 text-2xl font-medium">Bulk Email</h1>
            <p className="mt-2 text-slate-500 dark:text-slate-400">
                Send newsletters and statements to members by email.
            </p>
            <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
                This module is not available yet — the API has not been implemented.
            </p>
            <Link className="mt-6 inline-block text-green-700 underline dark:text-green-400" to="/">
                Go to dashboard
            </Link>
        </div>
    )
}