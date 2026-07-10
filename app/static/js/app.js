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


// Loading skeleton: add a shimmer class to recipe images until they finish loading
(function () {
  document.querySelectorAll('.recipe-card img, .recipe-row img').forEach(function (img) {
    if (!img.complete) {
      img.classList.add('skeleton');
      img.addEventListener('load', function () {
        img.classList.remove('skeleton');
      });
    }
  });
})();

// Sticky navbar shadow + back-to-top button
(function () {
  const header = document.querySelector(".site-header");
  const backToTop = document.querySelector("#back-to-top");

  function onScroll() {
    if (header) {
      header.classList.toggle("scrolled", window.scrollY > 10);
    }
    if (backToTop) {
      backToTop.classList.toggle("visible", window.scrollY > 400);
    }
  }

  window.addEventListener("scroll", onScroll);
  onScroll();

  if (backToTop) {
    backToTop.addEventListener("click", function () {
      window.scrollTo({ top: 0, behavior: "smooth" });
    });
  }
})();
