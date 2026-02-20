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
  stability_score_norm?: number;
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

interface WaveDataRow {
  date: string;
  period_days: number;
  component_value: number;
}

type CycleSortKey = 'period_days' | 'norm_power' | 'presence_ratio' | 'stability';
type SortDirection = 'asc' | 'desc';

function paddedAxisRange(value: { min: number; max: number }, isMax: boolean) {
  const span = value.max - value.min;
  const padding = span > 0 ? span * 0.03 : Math.max(Math.abs(value.max || 1) * 0.03, 1e-6);
  return isMax ? value.max + padding : value.min - padding;
}

function periodKey(period: number) {
  return period.toFixed(6);
}

// --- Main Dashboard Component ---
function Dashboard({ defaultSeries = '' }: { defaultSeries?: string }) {
  // Using hardcoded series list as we dropped the API proxying this logic. We could fetch from /data/latest/summary.json globally
  const [seriesId, setSeriesId] = useState(defaultSeries);
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [priceData, setPriceData] = useState<[string, number][]>([]);
  const [spectrumData, setSpectrumData] = useState<[number, number][]>([]);
  const [allStableCycles, setAllStableCycles] = useState<CycleData[]>([]);
  const [waveDataByPeriod, setWaveDataByPeriod] = useState<Record<string, [string, number][]>>({});
  const [wavesError, setWavesError] = useState<string | null>(null);

  // UI State
  const [selectedCycles, setSelectedCycles] = useState<Set<string>>(new Set());
  const [isSuperpose, setIsSuperpose] = useState(true);
  const [sortKey, setSortKey] = useState<CycleSortKey>('period_days');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');
  const maxLegacyStability = useMemo(
    () => allStableCycles.reduce((maxValue, cycle) => Math.max(maxValue, cycle.stability_score || 0), 0),
    [allStableCycles]
  );

  // Load static data files
  useEffect(() => {
    if (!seriesId) return;

    // Reset state on series change
    setSummary(null);
    setPriceData([]);
    setSpectrumData([]);
    setWaveDataByPeriod({});
    setWavesError(null);
    setSelectedCycles(new Set());

    // 1. Fetch Summary
    fetch(`/assets/data/latest/${seriesId}/summary.json`)
      .then(res => res.json())
      .then(data => {
        setSummary(data);
        const defaults = Array.isArray(data?.selected_cycles)
          ? data.selected_cycles
            .map((cycle: CycleData) => periodKey(cycle.period_days))
          : [];
        setSelectedCycles(new Set(defaults));
      })
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
        setAllStableCycles(stableOnly);
      }
    });

    // 5. Fetch per-cycle component waves exported by the backend
    Papa.parse<WaveDataRow>(`/assets/data/latest/${seriesId}/waves.csv`, {
      download: true,
      header: true,
      dynamicTyping: true,
      skipEmptyLines: true,
      complete: (results) => {
        const grouped: Record<string, [string, number][]> = {};
        results.data.forEach((row) => {
          if (!row.date || typeof row.period_days !== 'number' || typeof row.component_value !== 'number') return;
          const key = periodKey(row.period_days);
          if (!grouped[key]) grouped[key] = [];
          grouped[key].push([row.date, row.component_value]);
        });
        Object.values(grouped).forEach(series =>
          series.sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
        );
        setWaveDataByPeriod(grouped);
        if (Object.keys(grouped).length === 0) {
          setWavesError('No wave components found in waves.csv (rerun pipeline).');
        } else {
          setWavesError(null);
        }
      },
      error: (error) => {
        console.error('Waves load error:', error);
        setWaveDataByPeriod({});
        setWavesError('waves.csv missing or unreadable (rerun pipeline).');
      }
    });

  }, [seriesId]);

  // Toggle cycle selection
  const toggleCycle = (period: number) => {
    const key = periodKey(period);
    const newSet = new Set(selectedCycles);
    if (newSet.has(key)) newSet.delete(key);
    else newSet.add(key);
    setSelectedCycles(newSet);
  };

  // Generate color palette for cycles to keep them distinct
  const cycleColors = ["#f87171", "#34d399", "#60a5fa", "#fbbf24", "#a78bfa", "#f472b6", "#2dd4bf", "#e879f9"];
  const getCycleColor = (index: number) => cycleColors[index % cycleColors.length];
  const cycleColorByPeriod = useMemo(() => {
    const mapping: Record<string, string> = {};
    allStableCycles.forEach((cycle, index) => {
      mapping[periodKey(cycle.period_days)] = getCycleColor(index);
    });
    return mapping;
  }, [allStableCycles]);

  const getNormalizedStability = (cycle: CycleData) => {
    const normalizedStabilityRaw = typeof cycle.stability_score_norm === 'number'
      ? cycle.stability_score_norm
      : (maxLegacyStability > 0 ? cycle.stability_score / maxLegacyStability : 0);
    return Math.max(0, Math.min(1, normalizedStabilityRaw));
  };

  const sortedStableCycles = useMemo(() => {
    const sorted = [...allStableCycles];
    sorted.sort((a, b) => {
      const left = sortKey === 'period_days'
        ? a.period_days
        : sortKey === 'norm_power'
          ? a.norm_power
          : sortKey === 'presence_ratio'
            ? a.presence_ratio
            : getNormalizedStability(a);
      const right = sortKey === 'period_days'
        ? b.period_days
        : sortKey === 'norm_power'
          ? b.norm_power
          : sortKey === 'presence_ratio'
            ? b.presence_ratio
            : getNormalizedStability(b);

      if (left === right) return b.period_days - a.period_days;
      return sortDirection === 'asc' ? left - right : right - left;
    });
    return sorted;
  }, [allStableCycles, sortKey, sortDirection, maxLegacyStability]);

  const handleSort = (nextKey: CycleSortKey) => {
    if (sortKey === nextKey) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
      return;
    }
    setSortKey(nextKey);
    setSortDirection('desc');
  };

  const sortIndicator = (key: CycleSortKey) => {
    if (sortKey !== key) return '↕';
    return sortDirection === 'asc' ? '↑' : '↓';
  };


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

    const selectedWaveSeries = allStableCycles
      .filter(cycle => selectedCycles.has(periodKey(cycle.period_days)))
      .map((cycle, index) => ({
        cycle,
        color: cycleColorByPeriod[periodKey(cycle.period_days)] || getCycleColor(index),
        points: waveDataByPeriod[periodKey(cycle.period_days)] || []
      }))
      .filter(item => item.points.length > 0);

    if (selectedCycles.size > 0) {
      if (isSuperpose) {
        const byDate = new Map<string, number>();
        selectedWaveSeries.forEach(item => {
          item.points.forEach(([date, value]) => {
            byDate.set(date, (byDate.get(date) || 0) + value);
          });
        });
        const superposition = Array.from(byDate.entries())
          .map(([date, value]) => [date, value] as [string, number])
          .sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime());
        if (superposition.length > 0) {
          series.push({
            name: 'Superposition',
            type: 'line',
            data: superposition,
            showSymbol: false,
            lineStyle: { width: 2, color: '#fbbf24', type: 'dashed' },
            itemStyle: { color: '#fbbf24' },
            yAxisIndex: 1
          });
        }
      } else {
        selectedWaveSeries.forEach(item => {
          series.push({
            name: `Cycle ${item.cycle.period_days.toFixed(1)}d`,
            type: 'line',
            data: item.points,
            showSymbol: false,
            lineStyle: { width: 1.5, color: item.color, opacity: 0.85 },
            yAxisIndex: 1
          });
        });
      }
    }

    return {
      tooltip: { trigger: 'axis', backgroundColor: '#1e293b', borderColor: '#334155', textStyle: { color: '#fff' } },
      grid: { top: 40, right: 40, bottom: 20, left: 60, containLabel: false },
      xAxis: { type: 'time', splitLine: { show: true, lineStyle: { color: '#1e293b' } }, axisLabel: { color: '#94a3b8' } },
      yAxis: [
        {
          type: 'value',
          scale: true,
          min: (value: { min: number; max: number }) => paddedAxisRange(value, false),
          max: (value: { min: number; max: number }) => paddedAxisRange(value, true),
          splitLine: { show: true, lineStyle: { color: '#1e293b' } },
          axisLabel: { color: '#94a3b8' }
        },
        { type: 'value', scale: true, splitLine: { show: false }, axisLabel: { show: false } } // Secondary axis for overlays so they don't break price scale
      ],
      dataZoom: [{
        type: 'inside',
        xAxisIndex: [0],
        filterMode: 'filter',
        zoomOnMouseWheel: true,
        moveOnMouseWheel: false
      }],
      series: series,
      backgroundColor: 'transparent'
    };
  }, [priceData, selectedCycles, isSuperpose, allStableCycles, waveDataByPeriod, cycleColorByPeriod]);


  const spectrumChartOption = useMemo(() => {
    if (!spectrumData.length) return {};

    // Generate scatter points for the peaks highlighting
    const peakHighlights = allStableCycles
      .filter(c => selectedCycles.has(periodKey(c.period_days)))
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
      yAxis: {
        type: 'value',
        scale: true,
        min: (value: { min: number; max: number }) => paddedAxisRange(value, false),
        max: (value: { min: number; max: number }) => paddedAxisRange(value, true),
        splitLine: { show: true, lineStyle: { color: '#1e293b' } },
        axisLabel: { color: '#94a3b8' }
      },
      dataZoom: [
        {
          type: 'inside',
          xAxisIndex: [0],
          filterMode: 'filter',
          zoomOnMouseWheel: true,
          moveOnMouseWheel: false
        },
        { type: 'slider', xAxisIndex: [0], bottom: 0, height: 15, borderColor: 'transparent', handleSize: '100%' }
      ],
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
                  <th className="px-3 py-2 font-medium">
                    <button className="inline-flex items-center gap-1 hover:text-white" onClick={() => handleSort('period_days')}>
                      Period <span>{sortIndicator('period_days')}</span>
                    </button>
                  </th>
                  <th className="px-3 py-2 font-medium">
                    <button className="inline-flex items-center gap-1 hover:text-white" onClick={() => handleSort('norm_power')}>
                      Power <span>{sortIndicator('norm_power')}</span>
                    </button>
                  </th>
                  <th className="px-3 py-2 font-medium">
                    <button className="inline-flex items-center gap-1 hover:text-white" onClick={() => handleSort('presence_ratio')}>
                      Presence <span>{sortIndicator('presence_ratio')}</span>
                    </button>
                  </th>
                  <th className="px-3 py-2 font-medium">
                    <button className="inline-flex items-center gap-1 hover:text-white" onClick={() => handleSort('stability')}>
                      Stability (0-1) <span>{sortIndicator('stability')}</span>
                    </button>
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {sortedStableCycles.map((cycle) => {
                  const isSelected = selectedCycles.has(periodKey(cycle.period_days));
                  const drawColor = isSuperpose ? '#fbbf24' : cycleColorByPeriod[periodKey(cycle.period_days)] || '#fbbf24';
                  const normalizedStability = getNormalizedStability(cycle);
                  return (
                    <tr
                      key={periodKey(cycle.period_days)}
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
                        {normalizedStability.toFixed(3)}
                      </td>
                    </tr>
                  )
                })}
                {sortedStableCycles.length === 0 && (
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
            {wavesError ? ` | ${wavesError}` : ''}
          </div>

        </div>

      </div>
    </div>
  );
}
