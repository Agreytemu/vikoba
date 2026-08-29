import { FC } from "react";
import { Link } from "react-router-dom";

import Spinner from "@/components/Spinner";
import LucideIcon from "@/components/LucideIcon";
import { Badge } from "@/components/ui/badge";
import { useGetAnnouncements, useGetMeetings } from "@/hooks/api/community";

const Community: FC = () => {
  const { data: announcements, isLoading: annLoading } = useGetAnnouncements();
  const { data: meetings, isLoading: meetingsLoading } = useGetMeetings();

  const now = new Date();
  const upcoming = (meetings ?? []).filter((m) => new Date(m.starts_at) >= now);
  const past = (meetings ?? []).filter((m) => new Date(m.starts_at) < now);

  return (
    <div className="space-y-8">
      <div>
        <h1 className="font-display text-2xl font-semibold">Community</h1>
        <p className="text-sm text-slate-500 dark:text-slate-400">
          Announcements and meetings from the cooperative.
        </p>
      </div>

      <section>
        <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold">
          <LucideIcon name="Megaphone" size={20} /> Announcements
        </h2>
        {annLoading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : !announcements || announcements.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">
            No announcements yet.
          </p>
        ) : (
          <ul className="space-y-3">
            {announcements.map((a) => (
              <li key={a.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
                <div className="flex items-center justify-between gap-3">
                  <h3 className="flex items-center gap-2 font-display font-semibold">
                    {a.pinned && <LucideIcon name="Pin" size={16} className="text-blue-600 dark:text-blue-400" />}
                    {a.title}
                  </h3>
                  <Badge className="bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300">{a.status_display}</Badge>
                </div>
                <p className="mt-2 whitespace-pre-wrap text-sm text-slate-600 dark:text-slate-300">{a.body}</p>
                <p className="mt-3 text-xs text-slate-400 dark:text-slate-500">
                  {a.author_name} · {new Date(a.created_at).toLocaleDateString()}
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 flex items-center gap-2 font-display text-lg font-semibold">
          <LucideIcon name="Calendar" size={20} /> Meetings
        </h2>
        {meetingsLoading ? (
          <div className="flex justify-center py-10"><Spinner /></div>
        ) : upcoming.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-slate-300 p-8 text-center text-sm text-slate-500 dark:border-slate-700">
            No upcoming meetings scheduled.
          </p>
        ) : (
          <ul className="space-y-3">
            {upcoming.map((m) => (
              <li key={m.id} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-card dark:border-slate-800 dark:bg-slate-900">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="font-display font-semibold">{m.title}</h3>
                    <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                      {new Date(m.starts_at).toLocaleString([], { dateStyle: "medium", timeStyle: "short" })}
                      {m.location ? ` · ${m.location}` : ""}
                    </p>
                  </div>
                  <Badge className="bg-green-100 text-green-800 dark:bg-green-950/60 dark:text-green-300">Upcoming</Badge>
                </div>
                {m.description && (
                  <p className="mt-2 text-sm text-slate-600 dark:text-slate-300">{m.description}</p>
                )}
              </li>
            ))}
          </ul>
        )}
        {past.length > 0 && (
          <details className="mt-4 rounded-2xl border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
            <summary className="cursor-pointer text-sm font-medium text-slate-600 dark:text-slate-300">
              Past meetings ({past.length})
            </summary>
            <ul className="mt-3 space-y-2">
              {past.map((m) => (
                <li key={m.id} className="text-sm">
                  <span className="font-medium">{m.title}</span>
                  <span className="text-slate-500"> — {new Date(m.starts_at).toLocaleDateString()}</span>
                </li>
              ))}
            </ul>
          </details>
        )}
      </section>

      <p className="text-sm text-slate-400 dark:text-slate-500">
        Questions? <Link className="underline" to="/help">Visit help</Link>
      </p>
    </div>
  );
};

export default Community;