export function applyTaskStatistics(metrics, statistics) {
  if (!statistics) return false;
  const running = Number.isInteger(statistics.active) ? statistics.active : (Number.isInteger(statistics.running) ? statistics.running : null);
  if (
    !Number.isInteger(statistics.total) || statistics.total < 0 ||
    running === null || running < 0 ||
    !Number.isInteger(statistics.done) || statistics.done < 0 ||
    !Number.isInteger(statistics.abnormal) || statistics.abnormal < 0
  ) {
    return false;
  }
  metrics.total = statistics.total;
  metrics.running = running;
  metrics.done = statistics.done;
  metrics.abnormal = statistics.abnormal;
  return true;
}

export function createTaskListClient(request) {
  const pending = new Map();
  return {
    get(endpoint, params = {}, includeStatistics = true) {
      const query = includeStatistics ? { ...params, include_statistics: 1 } : { ...params };
      const key = JSON.stringify([endpoint, Object.keys(query).sort().map(name => [name, query[name]])]);
      if (pending.has(key)) return pending.get(key);
      const result = Promise.resolve().then(() => request.get(endpoint, { params: query }));
      pending.set(key, result);
      const cleanup = () => {
        if (pending.get(key) === result) pending.delete(key);
      };
      result.then(cleanup, cleanup);
      return result;
    }
  };
}
