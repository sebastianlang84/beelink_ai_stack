import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { useEffect, useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import Papa from 'papaparse';

// Base layout structures
export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen w-screen bg-slate-950 text-slate-200 overflow-hidden font-sans select-none">
        <Routes>
          <Route path="/" element={<Dashboard defaultSeries="yahoo-spy" />} />
          <Route path="/series/:seriesId" element={<Dashboard />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}

// --- Types ---
interface CycleData {
  period_days: number;
  norm_power: number;
  presence_ratio: number;
  stability_score: number;
  stable: boolean;
}

interface SummaryData {
  series: string;
  source: string;
  points: number;
  timeframe_days: number;
  stable_cycle_count: number;
  selected_cycles: CycleData[];
}

interface PriceDataRow {
  date: string;
  value: number;
}

interface SpectrumDataRow {
  period_days: number;
  norm_power: number;
}

// --- Main Dashboard Component ---
function Dashboard({ defaultSeries = '' }: { defaultSeries?: string }) {
  // Using hardcoded series list as we dropped the API proxying this logic. We could fetch from /data/latest/summary.json globally
  const [seriesId, setSeriesId] = useState(defaultSeries);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [priceData, setPriceData] = useState<[string, number][]>([]);
  const [spectrumData, setSpectrumData] = useState<[number, number][]>([]);
  const [allStableCycles, setAllStableCycles] = useState<CycleData[]>([]);

  // UI State
  const [selectedCycles, setSelectedCycles] = useState<Set<number>>(new Set());
  const [isSuperpose, setIsSuperpose] = useState(true);

  // Load static data files
  useEffect(() => {
    if (!seriesId) return;

    // Reset state on series change
    setSummary(null);
    setPriceData([]);
    setSpectrumData([]);
    setSelectedCycles(new Set());

    // 1. Fetch Summary
    fetch(`/assets/data/latest/${seriesId}/summary.json`)
      .then(res => res.json())
      .then(data => setSummary(data))
      .catch(e => console.error("Summary load error:", e));

    // 2. Fetch Price Series CSV
    Papa.parse<PriceDataRow>(`/assets/data/latest/${seriesId}/series.csv`, {
      download: true,
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        // results.data = [{date: "2023-02-21", value: 399.08}, ...]
        const parsed = results.data.map(r => [r.date, r.value] as [string, number]);
        setPriceData(parsed);
      }
    });

    // 3. Fetch Spectrum CSV
    Papa.parse<SpectrumDataRow>(`/assets/data/latest/${seriesId}/spectrum.csv`, {
      download: true,
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        // periods on X axis, power on Y
        const parsed = results.data
          .filter(r => r.period_days <= 365) // Filter out noise for UI clarity
          .map(r => [r.period_days, r.norm_power] as [number, number])
          .sort((a, b) => a[0] - b[0]);
        setSpectrumData(parsed);
      }
    });

    // 4. Fetch All Stable Cycles (since summary only has Top K selected cycles)
    // We want the user to pick from ALL stable ones.
    Papa.parse<CycleData>(`/assets/data/latest/${seriesId}/cycles.csv`, {
      download: true,
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        const stableOnly = results.data.filter(c => c.stable === true || String(c.stable).toLowerCase() === 'true');
        // Sort by period descending
        stableOnly.sort((a, b) => b.period_days - a.period_days);
        setAllStableCycles(stableOnly);
      }
    });

  }, [seriesId]);

  // Toggle cycle selection
  const toggleCycle = (period: number) => {
    const newSet = new Set(selectedCycles);
    if (newSet.has(period)) newSet.delete(period);
    else newSet.add(period);
    setSelectedCycles(newSet);
  };

  // Generate color palette for cycles to keep them distinct
  const cycleColors = ["#f87171", "#34d399", "#60a5fa", "#fbbf24", "#a78bfa", "#f472b6", "#2dd4bf", "#e879f9"];
  const getCycleColor = (index: number) => cycleColors[index % cycleColors.length];


  // --- ECharts Options Generation ---

  const priceChartOption = useMemo(() => {
    if (!priceData.length) return {};

    const series: any[] = [
      {
        name: 'Price',
        type: 'line',
        data: priceData,
        showSymbol: false,
        lineStyle: { color: '#64748b', width: 2 },
        itemStyle: { color: '#64748b' }
      }
    ];

    // TODO: In Phase C Option A, we would load the 'waves.csv' here and overlay the actual vectors.
    // For now, since we haven't updated the Python backend to export waves.csv yet, 
    // we will just draw the layout, and I will simulate a flat line overlay to prove the UI works.

    // Simulate overlay reading 
    if (selectedCycles.size > 0) {
      if (isSuperpose) {
        series.push({
          name: 'Superposition (Mock)',
          type: 'line',
          data: priceData.map(p => [p[0], p[1] * 1.01]), // Mock shift
          showSymbol: false,
          lineStyle: { width: 2, color: '#fbbf24', type: 'dashed' },
          itemStyle: { color: '#fbbf24' },
          yAxisIndex: 1
        });
      } else {
        let cIdx = 0;
        allStableCycles.forEach(cycle => {
          if (selectedCycles.has(cycle.period_days)) {
            series.push({
              name: `Cycle ${cycle.period_days.toFixed(1)}d`,
              type: 'line',
              data: priceData.map((p, i) => [p[0], priceData[0][1] + Math.sin(i * (Math.PI * 2 / cycle.period_days)) * priceData[0][1] * cycle.norm_power * 10]), // Mock wave visually mapped to price
              showSymbol: false,
              lineStyle: { width: 1.5, color: getCycleColor(cIdx), opacity: 0.8 },
              yAxisIndex: 1
            });
            cIdx++;
          }
        });
      }
    }

    return {
      tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#fff' } },
      grid: { top: 40, right: 40, bottom: 20, left: 60, containLabel: false },
      xAxis: { type: 'time', splitLine: { show: true, lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        { type: 'value', min: 'dataMin', max: 'dataMax', splitLine: { show: true, lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8' } },
        { type: 'value', splitLine: { show: false }, axisLabel: { show: false } } // Secondary axis for overlays so they don't break price scale
      ],
      dataZoom: [{ type: 'inside' }],
      series: series,
      backgroundColor: 'transparent'
    };
  }, [priceData, selectedCycles, isSuperpose, allStableCycles]);


  const spectrumChartOption = useMemo(() => {
    if (!spectrumData.length) return {};

    // Generate scatter points for the peaks highlighting
    const peakHighlights = allStableCycles
      .filter(c => selectedCycles.has(c.period_days))
      .map(c => [c.period_days, c.norm_power]);

    return {
      tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#fff' } },
      grid: { top: 20, right: 40, bottom: 40, left: 60, containLabel: false },
      xAxis: {
        type: 'value',
        name: 'Period (Days)',
        nameLocation: 'middle',
        nameGap: 30,
        splitLine: { show: true, lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      },
      yAxis: { type: 'value', splitLine: { show: true, lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8' } },
      dataZoom: [{ type: 'inside' }, { type: 'slider', bottom: 0, height: 15, borderColor: 'transparent', handleSize: '100%' }],
      series: [
        {
          name: 'Power',
          type: 'line',
          data: spectrumData,
          showSymbol: false,
          areaStyle: {
            color: {
              type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
              colorStops: [{ offset: 0, color: '#3b82f650' }, { offset: 1, color: '#3b82f605' }]
            }
          },
          lineStyle: { color: '#3b82f6', width: 2 },
          itemStyle: { color: '#3b82f6' }
        },
        {
          name: 'Selected Peaks',
          type: 'scatter',
          data: peakHighlights,
          symbolSize: 10,
          itemStyle: { color: '#fbbf24' } // Yellow dots for selected cycles
        }
      ],
      backgroundColor: 'transparent'
    };
  }, [spectrumData, selectedCycles, allStableCycles]);


  return (
    <div className="flex flex-col w-full h-full p-2 gap-2">
      {/* Header Minimalist */}
      <div className="flex justify-between items-center h-12 bg-slate-900 border border-slate-800 rounded px-4 shrink-0 shadow-sm">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold tracking-tight text-white">Fourier Cycles</h1>
          <span className="text-slate-500 font-mono text-sm">{summary ? `${summary.source.toUpperCase()}:${summary.series}` : 'Loading...'}</span>
        </div>
        <div className="flex gap-2">
          {/* Mock Series Switcher for Demo */}
          <select
            className="bg-slate-800 border-none text-slate-200 text-sm rounded outline-none px-2 py-1 cursor-pointer focus:ring-1 focus:ring-slate-600"
            value={seriesId}
            onChange={(e) => setSeriesId(e.target.value)}
          >
            <option value="yahoo-spy">S&P 500 (SPY)</option>
            <option value="yahoo-btc-usd">Bitcoin (BTC)</option>
            <option value="fred-dgs10">10Y Treasury (DGS10)</option>
          </select>
        </div>
      </div>

      {/* Main Grid View */}
      <div className="flex flex-1 overflow-hidden gap-2">

        {/* Left Column: Charts */}
        <div className="flex flex-col w-[70%] h-full gap-2">
          {/* Top: Price */}
          <div className="h-[65%] w-full bg-slate-900 border border-slate-800 rounded flex flex-col relative shadow-sm">
            <div className="absolute top-2 left-4 z-10 font-medium text-slate-400 text-sm">Price Extract & Overlays</div>
            <div className="flex-1 w-full h-full p-2 pt-6">
              {priceData.length > 0 ? (
                <ReactECharts option={priceChartOption} style={{ height: '100%', width: '100%' }} notMerge={true} />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-600">Loading chart data...</div>
              )}
            </div>
          </div>

          {/* Bottom: Spectrum */}
          <div className="h-[35%] w-full bg-slate-900 border border-slate-800 rounded flex flex-col relative shadow-sm">
            <div className="absolute top-2 left-4 z-10 font-medium text-slate-400 text-sm">Frequency Spectrum</div>
            <div className="flex-1 w-full h-full p-2 pt-6">
              {spectrumData.length > 0 ? (
                <ReactECharts option={spectrumChartOption} style={{ height: '100%', width: '100%' }} notMerge={true} />
              ) : (
                <div className="w-full h-full flex items-center justify-center text-slate-600">Loading spectrum...</div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Table & Controls */}
        <div className="flex flex-col w-[30%] h-full bg-slate-900 border border-slate-800 rounded shadow-sm overflow-hidden">

          <div className="p-3 border-b border-slate-800 flex justify-between items-center bg-slate-900/50">
            <h2 className="font-semibold text-slate-300">Extracted Cycles</h2>

            {/* Global Toggle Controls */}
            <div className="flex bg-slate-950 rounded p-1 border border-slate-800">
              <button
                onClick={() => setIsSuperpose(true)}
                className={`px-3 py-1 text-xs rounded transition-colors ${isSuperpose ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                Superpose
              </button>
              <button
                onClick={() => setIsSuperpose(false)}
                className={`px-3 py-1 text-xs rounded transition-colors ${!isSuperpose ? 'bg-indigo-600 text-white' : 'text-slate-400 hover:text-white'}`}
              >
                Individual
              </button>
            </div>
          </div>

          {/* Table Scrollable Container */}
          <div className="flex-1 overflow-y-auto">
            <table className="w-full text-left text-sm text-slate-400 border-collapse">
              <thead className="sticky top-0 bg-slate-900 shadow-md z-10 outline outline-1 outline-slate-800">
                <tr>
                  <th className="px-3 py-2 font-medium w-8 text-center">+/-</th>
                  <th className="px-3 py-2 font-medium">Period</th>
                  <th className="px-3 py-2 font-medium">Power</th>
                  <th className="px-3 py-2 font-medium">Presence</th>
                  <th className="px-3 py-2 font-medium">Stability</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {allStableCycles.map((cycle, i) => {
                  const isSelected = selectedCycles.has(cycle.period_days);
                  const drawColor = isSuperpose ? '#fbbf24' : getCycleColor(i);
                  return (
                    <tr
                      key={i}
                      className={`hover:bg-slate-800/50 transition-colors cursor-pointer ${isSelected ? 'bg-slate-800/30' : ''}`}
                      onClick={() => toggleCycle(cycle.period_days)}
                    >
                      <td className="px-3 py-2 text-center">
                        <input
                          type="checkbox"
                          className="accent-indigo-500 w-4 h-4 cursor-pointer"
                          checked={isSelected}
                          readOnly
                        />
                      </td>
                      <td className="px-3 py-2 font-semibold text-slate-200 flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: isSelected ? drawColor : 'transparent' }}></div>
                        {cycle.period_days.toFixed(1)}d
                      </td>
                      <td className="px-3 py-2 font-mono text-indigo-400">
                        {cycle.norm_power.toFixed(3)}
                      </td>
                      <td className="px-3 py-2">
                        {(cycle.presence_ratio * 100).toFixed(0)}%
                      </td>
                      <td className="px-3 py-2">
                        {cycle.stability_score.toFixed(3)}
                      </td>
                    </tr>
                  )
                })}
                {allStableCycles.length === 0 && (
                  <tr>
                    <td colSpan={5} className="px-4 py-8 text-center text-slate-600">
                      No stable cycles found or still loading.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="p-3 border-t border-slate-800 text-xs text-slate-600 text-center bg-slate-900/80">
            Total stable: {allStableCycles.length} | Selected: {selectedCycles.size}
          </div>

        </div>

      </div>
    </div>
  );
}
