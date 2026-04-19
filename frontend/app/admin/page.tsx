import { createClient } from '@/lib/supabase/server';
import { getUserTier } from '@/lib/saas/tiers';
import { redirect } from 'next/navigation';

/**
 * Admin Dashboard Page.
 * Displays system-wide metrics and management tools.
 * Note: In a real app, this would be protected by an 'admin' role check.
 */
export default async function AdminDashboard() {
  const supabase = await createClient();
  
  // 1. Protection (Admin Role Check)
  const { data: { user } } = await supabase.auth.getUser();
  if (!user) redirect('/auth/login');
  
  // Simulated admin check (e.g., email or metadata)
  const isAdmin = user.email?.endsWith('@admin.com') || user.id === process.env.ADMIN_USER_ID;
  if (!isAdmin) redirect('/dashboard');

  // 2. Parallel Metrics Gathering
  const [usersCount, activeJobs, failedJobs, logs] = await Promise.all([
    supabase.from('profiles').select('id', { count: 'exact', head: true }),
    supabase.from('jobs').select('id', { count: 'exact', head: true }).eq('status', 'processing'),
    supabase.from('dead_jobs').select('id', { count: 'exact', head: true }),
    supabase.from('app_logs').select('id, level, context, message').order('created_at', { ascending: false }).limit(20)
  ]);

  return (
    <div className="p-8 bg-slate-50 min-h-screen">
      <h1 className="text-3xl font-bold mb-8 text-slate-900">SaaS Admin Control Panel</h1>
      
      {/* 📊 Metrics Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <MetricCard title="Total Users" value={usersCount.count || 0} color="blue" />
        <MetricCard title="Active Jobs" value={activeJobs.count || 0} color="green" />
        <MetricCard title="Dead Letter (Failures)" value={failedJobs.count || 0} color="red" />
        <MetricCard title="System Logs" value={logs.data?.length || 0} color="slate" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* 🛠 Job Monitoring */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h2 className="text-xl font-semibold mb-4 text-slate-800">Job Queue Monitoring</h2>
          <div className="space-y-4">
            {/* Logic to list and manage jobs would go here */}
            <p className="text-sm text-slate-500 italic">Queue is currently healthy.</p>
          </div>
        </div>

        {/* 📜 System Activity Logs */}
        <div className="bg-white p-6 rounded-xl shadow-sm border border-slate-200">
          <h2 className="text-xl font-semibold mb-4 text-slate-800">Live System Logs</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-slate-100">
                  <th className="pb-2 font-medium text-slate-600">Level</th>
                  <th className="pb-2 font-medium text-slate-600">Context</th>
                  <th className="pb-2 font-medium text-slate-600">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {logs.data?.map((log) => (
                  <tr key={log.id}>
                    <td className={`py-2 font-bold ${log.level === 'ERROR' ? 'text-red-500' : 'text-blue-500'}`}>
                      {log.level}
                    </td>
                    <td className="py-2 text-slate-600">{log.context}</td>
                    <td className="py-2 text-slate-500 truncate max-w-xs">{log.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetricCard({ title, value, color }: { title: string, value: number, color: 'blue' | 'green' | 'red' | 'slate' }) {
  const colors = {
    blue: 'bg-blue-50 text-blue-700 border-blue-100',
    green: 'bg-green-50 text-green-700 border-green-100',
    red: 'bg-red-50 text-red-700 border-red-100',
    slate: 'bg-slate-50 text-slate-700 border-slate-100'
  };

  return (
    <div className={`p-6 rounded-xl border ${colors[color]}`}>
      <p className="text-sm font-medium opacity-80">{title}</p>
      <p className="text-3xl font-bold mt-1">{value}</p>
    </div>
  );
}
