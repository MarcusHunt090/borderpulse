/* Calendar-aware transformations for the standalone data explorer.
   This file is embedded by build.py; it also runs in Node's test runner. */
const Explorer = (() => {
  const modes = new Set(['level', 'yoy', 'difference']);
  function shift(month, count) {
    const [year, number] = month.split('-').map(Number);
    const date = new Date(Date.UTC(year, number - 1 + count, 1));
    return date.toISOString().slice(0, 7);
  }
  function calendar(first, last) {
    const result = [];
    for (let month = first; month <= last; month = shift(month, 1)) result.push(month);
    return result;
  }
  function catalog(csv, manifest) {
    const values = new Map();
    csv.trim().split(/\r?\n/).slice(1).forEach(row => {
      const [id, date, raw] = row.split(',');
      if (!raw || !Number.isFinite(Number(raw))) return;
      if (!values.has(id)) values.set(id, {});
      values.get(id)[date.slice(0, 7)] = Number(raw);
    });
    return (manifest?.files || []).filter(file => {
      const id = file.file.replace(/^data\//, '').replace(/\.csv$/, '');
      return !id.startsWith('pre2015/') && values.has(id) &&
        (id.includes('/') || !values.has('full/' + id));
    }).map(file => {
      const id = file.file.replace(/^data\//, '').replace(/\.csv$/, '');
      return { ...file, id, label: file.description || id, values: values.get(id) };
    }).sort((a, b) => a.label.localeCompare(b.label));
  }
  function select(values, mode, first, last) {
    if (!modes.has(mode)) throw new Error('Unknown explorer transformation');
    const months = Object.keys(values).sort();
    if (!months.length || first > last) return [];
    return calendar(months[0], months[months.length - 1]).filter(m => m >= first && m <= last).map(month => {
      const current = values[month], previous = values[shift(month, -12)];
      let value = Number.isFinite(current) ? current : null;
      if (mode !== 'level') {
        value = Number.isFinite(current) && Number.isFinite(previous) && (mode !== 'yoy' || previous !== 0)
          ? (mode === 'yoy' ? 100 * (current / previous - 1) : current - previous) : null;
      }
      return [month, value];
    });
  }
  function segments(points) {
    const result = [];
    let run = [];
    points.forEach((point, index) => {
      if (Number.isFinite(point[1])) run.push([index, point[1]]);
      else if (run.length) { result.push(run); run = []; }
    });
    if (run.length) result.push(run);
    return result;
  }
  function csv(series, mode, points) {
    const quote = value => '"' + String(value).replace(/"/g, '""') + '"';
    const header = ['series', 'series_id', 'month', 'transformation', 'value', 'description', 'source', 'retrieved'];
    return header.join(',') + '\n' + points.map(([month, value]) =>
      [series.id, series.series_id, month, mode, value ?? '', series.label || series.id, series.source, series.retrieved].map(quote).join(',')
    ).join('\n') + '\n';
  }
  return { shift, calendar, catalog, select, segments, csv };
})();
if (typeof module !== 'undefined' && module.exports) module.exports = Explorer;
