chrome.runtime.onInstalled.addListener(() => {
  console.log("Tracker Blocker installed.");
});

chrome.declarativeNetRequest.onRuleMatchedDebug.addListener((info) => {
  chrome.storage.local.get({ blocked: 0 }, (data) => {
    let updated = data.blocked + 1;
    chrome.storage.local.set({ blocked: updated });
    chrome.action.setBadgeText({ text: updated.toString() });
  });
});
