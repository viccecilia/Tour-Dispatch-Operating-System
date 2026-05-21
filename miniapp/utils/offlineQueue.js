const QUEUE_KEY = 'driver_offline_tasks_v1';

function nowId() {
  return `${Date.now()}_${Math.random().toString(16).slice(2)}`;
}

function readQueue() {
  return wx.getStorageSync(QUEUE_KEY) || [];
}

function writeQueue(queue) {
  wx.setStorageSync(QUEUE_KEY, queue);
  return queue;
}

function enqueue(type, payload) {
  const queue = readQueue();
  const task = {
    id: nowId(),
    type,
    payload,
    created_at: Date.now(),
    retry_count: 0,
    last_error: ''
  };
  queue.push(task);
  writeQueue(queue);
  return task;
}

function count(driverId) {
  return list(driverId).length;
}

function list(driverId) {
  const queue = readQueue();
  if (!driverId) return queue;
  return queue.filter((task) => Number(task.payload && task.payload.driver_id) === Number(driverId));
}

function clearDone(doneIds) {
  const done = new Set(doneIds);
  return writeQueue(readQueue().filter((task) => !done.has(task.id)));
}

function updateTask(taskId, patch) {
  return writeQueue(readQueue().map((task) => (
    task.id === taskId ? { ...task, ...patch } : task
  )));
}

module.exports = {
  enqueue,
  count,
  list,
  clearDone,
  updateTask
};
