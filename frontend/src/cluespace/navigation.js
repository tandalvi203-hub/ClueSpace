/**
 * ClueSpace Navigation Controller
 * Manages 3-destination vertical timeline with animated circumference rotating light
 * and active investigation state across screens.
 */

let currentScreenIndex = 0;
let currentInvestigationId = null;

const screenKeys = [
  'screen-mission-control',
  'screen-incident-explorer',
  'screen-investigation-workspace'
];

let screenChangeListeners = [];
let investigationChangeListeners = [];

export function onScreenChange(fn) {
  screenChangeListeners.push(fn);
}

export function onInvestigationChange(fn) {
  investigationChangeListeners.push(fn);
}

export function getSelectedInvestigationId() {
  return currentInvestigationId;
}

export function setSelectedInvestigationId(id) {
  if (id !== currentInvestigationId) {
    currentInvestigationId = id;
    investigationChangeListeners.forEach(fn => {
      try {
        fn(currentInvestigationId);
      } catch (e) {
        console.error(e);
      }
    });
  }
}

export function clearSelectedInvestigation() {
  setSelectedInvestigationId(null);
}

export function navigateToInvestigationWorkspace(id) {
  if (id) {
    setSelectedInvestigationId(id);
  }
  navigateToScreen('screen-investigation-workspace');
}

export function getCurrentScreenKey() {
  return screenKeys[currentScreenIndex];
}

export function navigateToScreen(screenKeyOrIndex) {
  let targetIndex = 0;
  if (typeof screenKeyOrIndex === 'number') {
    targetIndex = screenKeyOrIndex;
  } else {
    targetIndex = screenKeys.indexOf(screenKeyOrIndex);
    if (targetIndex === -1) targetIndex = 0;
  }

  currentScreenIndex = targetIndex;

  // 1. Update Navigation Circles
  const navItems = document.querySelectorAll('.nav-timeline-item');
  navItems.forEach((item, idx) => {
    if (idx === targetIndex) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // 2. Update Content Screens
  screenKeys.forEach((key, idx) => {
    const screenEl = document.getElementById(key);
    if (screenEl) {
      if (idx === targetIndex) {
        screenEl.classList.add('active-screen');
      } else {
        screenEl.classList.remove('active-screen');
      }
    }
  });

  // 3. Notify subscribers
  screenChangeListeners.forEach(listener => {
    try {
      listener(screenKeys[targetIndex], targetIndex);
    } catch (e) {
      console.error(e);
    }
  });
}

export function initNavigation() {
  const navItems = document.querySelectorAll('.nav-timeline-item');
  navItems.forEach((item, idx) => {
    item.addEventListener('click', () => {
      navigateToScreen(idx);
    });
  });

  // Initial activation on screen 0 (Mission Control)
  navigateToScreen(0);
}
