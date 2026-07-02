const timerDisplay = document.querySelector("#timer");
const startButton = document.querySelector("[data-timer-start]");
const resetButton = document.querySelector("[data-timer-reset]");

let remainingSeconds = 25 * 60;
let timerId = null;

function renderTimer() {
  if (!timerDisplay) return;
  const minutes = Math.floor(remainingSeconds / 60).toString().padStart(2, "0");
  const seconds = (remainingSeconds % 60).toString().padStart(2, "0");
  timerDisplay.textContent = `${minutes}:${seconds}`;
}

function toggleTimer() {
  if (timerId) {
    clearInterval(timerId);
    timerId = null;
    startButton.textContent = "Start";
    return;
  }
  startButton.textContent = "Pause";
  timerId = setInterval(() => {
    remainingSeconds = Math.max(0, remainingSeconds - 1);
    renderTimer();
    if (remainingSeconds === 0) {
      clearInterval(timerId);
      timerId = null;
      startButton.textContent = "Start";
    }
  }, 1000);
}

if (startButton) {
  startButton.addEventListener("click", toggleTimer);
}

if (resetButton) {
  resetButton.addEventListener("click", () => {
    clearInterval(timerId);
    timerId = null;
    remainingSeconds = 25 * 60;
    startButton.textContent = "Start";
    renderTimer();
  });
}

renderTimer();
