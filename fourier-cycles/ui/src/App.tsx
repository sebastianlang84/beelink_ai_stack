import { BrowserRouter, Routes, Route, Link, useParams } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { LineChart, Table, AlertCircle, Activity, LayoutDashboard } from 'lucide-react';

interface SeriesData {
  id: string;
  source: string;
  name: string;
}

interface CycleData {
  period_days: number;
  norm_power: number;
  presence_ratio: number;
  stability_score: number;
}

interface SummaryData {
  series: string;
  source: string;
  points: number;
  selected_cycles: CycleData[];
}

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50 font-sans">
        {/* Sidebar */}
        <div className="w-64 bg-white border-r border-gray-200 flex flex-col">
          <div className="p-4 border-b border-gray-200">
            <h1 className="text-xl font-bold text-gray-800 flex items-center gap-2">
              <Activity className="w-6 h-6 text-indigo-600" />
              Fourier Cycles
            </h1>
          </div>
          <nav className="flex-1 overflow-y-auto p-4 flex flex-col gap-2">
            <Link to="/" className="flex items-center gap-3 px-3 py-2 text-gray-700 rounded-lg hover:bg-gray-100 transition-colors">
              <LayoutDashboard className="w-5 h-5" />
              Overview
            </Link>
            <div className="pt-4 pb-2">
              <span className="px-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">
                Latest Run Series
              </span>
            </div>
            <SeriesNavList />
          </nav>
        </div>

        {/* Main Content */}
        <div className="flex-1 overflow-hidden flex flex-col">
          <header className="bg-white border-b border-gray-200 px-8 py-4">
            <div className="flex justify-between items-center">
              <h2 className="text-xl font-semibold text-gray-800">Dashboard</h2>
            </div>
          </header>
          <main className="flex-1 overflow-auto p-8">
            <Routes>
              <Route path="/" element={<Overview />} />
              <Route path="/series/:seriesId" element={<SeriesDetail />} />
            </Routes>
          </main>
        </div>
      </div>
    </BrowserRouter>
  );
}

function SeriesNavList() {
  const [seriesList, setSeriesList] = useState<SeriesData[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch('/api/runs/latest/series')
      .then(res => res.json())
      .then(data => {
        if (data.series) {
          setSeriesList(data.series);
        }
      })
      .catch(err => {
        console.error('Failed to fetch series list', err);
        setError('Failed to load');
      });
  }, []);

  if (error) return <div className="px-3 py-2 text-red-500 text-sm">{error}</div>;

  return (
    <div className="flex flex-col gap-1">
      {seriesList.map((s) => (
        <Link
          key={s.id}
          to={`/series/${s.id}`}
          className="flex items-center gap-3 px-3 py-2 text-gray-600 rounded-lg hover:bg-indigo-50 hover:text-indigo-700 transition-colors"
        >
          <LineChart className="w-4 h-4" />
          <span className="truncate">{s.name} ({s.source})</span>
        </Link>
      ))}
      {seriesList.length === 0 && (
        <div className="px-3 py-2 text-gray-400 text-sm">No series found</div>
      )}
    </div>
  );
}

function Overview() {
  return (
    <div className="max-w-4xl">
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <h3 className="text-lg font-semibold text-gray-800 mb-2">Welcome to Fourier Cycles</h3>
        <p className="text-gray-600">
          Select a series from the left sidebar to view the interactive charts and cycle stability metrics.
        </p>
      </div>
    </div>
  );
}

function SeriesDetail() {
  const { seriesId } = useParams();
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [error, setError] = useState('');

  useEffect(() => {
    fetch(`/api/runs/latest/series/${seriesId}`)
      .then(res => {
        if (!res.ok) throw new Error('Not found');
        return res.json();
      })
      .then(data => setSummary(data))
      .catch(err => {
        console.error(err);
        setError('Failed to load series details');
      });
  }, [seriesId]);

  if (error) {
    return (
      <div className="bg-red-50 text-red-700 p-4 rounded-lg flex items-center gap-2">
        <AlertCircle className="w-5 h-5" />
        {error}
      </div>
    );
  }

  if (!summary) return <div className="text-gray-500">Loading...</div>;

  const cycles = summary.selected_cycles || [];

  return (
    <div className="flex flex-col gap-6">
      <div className="flex justify-between items-end">
        <div>
          <h2 className="text-2xl font-bold text-gray-900">{summary.series}</h2>
          <p className="text-gray-500">{summary.source} &bull; {summary.points} points</p>
        </div>
      </div>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
        {/* Left Side: Charts */}
        <div className="xl:col-span-2 flex flex-col gap-6">
          <ChartCard title="Price & Cycle Overlay" src={`/data/latest/${seriesId}/price_cycle_overlay.png`} />
          <ChartCard title="Frequency Spectrum" src={`/data/latest/${seriesId}/spectrum.png`} />
          <div className="grid grid-cols-2 gap-6">
            <ChartCard title="Cycle Components" src={`/data/latest/${seriesId}/cycle_components.png`} />
            <ChartCard title="Stability" src={`/data/latest/${seriesId}/stability.png`} />
          </div>
          <ChartCard title="Raw Price" src={`/data/latest/${seriesId}/price.png`} />
          <ChartCard title="Signal Reconstruction" src={`/data/latest/${seriesId}/reconstruction.png`} />
        </div>

        {/* Right Side: Data Table */}
        <div className="xl:col-span-1">
          <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden sticky top-0">
            <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
              <h3 className="font-semibold text-gray-800 flex items-center gap-2">
                <Table className="w-5 h-5" />
                Selected Cycles
              </h3>
            </div>
            <div className="p-0">
              <table className="w-full text-left text-sm text-gray-600">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 font-medium">Period (Days)</th>
                    <th className="px-4 py-3 font-medium">Power</th>
                    <th className="px-4 py-3 font-medium">Presence</th>
                    <th className="px-4 py-3 font-medium">Stability</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {cycles.map((cycle, i) => (
                    <tr key={i} className="hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-3 font-semibold text-gray-900">
                        {cycle.period_days.toFixed(1)}
                      </td>
                      <td className="px-4 py-3 text-indigo-600 font-mono">
                        {cycle.norm_power.toFixed(3)}
                      </td>
                      <td className="px-4 py-3">
                        {(cycle.presence_ratio * 100).toFixed(0)}%
                      </td>
                      <td className="px-4 py-3">
                        {cycle.stability_score.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                  {cycles.length === 0 && (
                    <tr>
                      <td colSpan={4} className="px-4 py-8 text-center text-gray-400">
                        No stable cycles found.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function ChartCard({ title, src }: { title: string, src: string }) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
      <div className="px-6 py-3 border-b border-gray-100 bg-gray-50/50">
        <h3 className="font-medium text-gray-700">{title}</h3>
      </div>
      <div className="p-4 bg-white flex justify-center">
        <img
          src={src}
          alt={title}
          className="max-w-full h-auto rounded object-contain max-h-[500px]"
          loading="lazy"
        />
      </div>
    </div>
  );
}

export default App;
