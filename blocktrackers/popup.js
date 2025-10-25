document.addEventListener('DOMContentLoaded', () => {
  const countEl = document.getElementById('count');

  chrome.storage.local.get('blocked', (data) => {
    countEl.textContent = data.blocked || 0;
  });

  document.getElementById('reset').addEventListener('click', () => {
    chrome.storage.local.set({ blocked: 0 });
    countEl.textContent = 0;
  });
});
