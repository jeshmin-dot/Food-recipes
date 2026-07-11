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

// Share button: native Web Share API where the browser supports it,
// falling back to copying the link to the clipboard (and a plain prompt()
// if even that isn't available) so the button always does something useful.
(function () {
  document.querySelectorAll("[data-share-button]").forEach(function (button) {
    button.addEventListener("click", async function () {
      const title = button.dataset.shareTitle || document.title;
      const url = button.dataset.shareUrl || window.location.href;

      if (navigator.share) {
        try {
          await navigator.share({ title: title, url: url });
        } catch (err) {
          // User closed the share sheet without picking anything - fine.
        }
        return;
      }

      try {
        await navigator.clipboard.writeText(url);
        const original = button.textContent;
        button.textContent = "Link copied!";
        setTimeout(function () {
          button.textContent = original;
        }, 2000);
      } catch (err) {
        window.prompt("Copy this link:", url);
      }
    });
  });
})();

// Ingredient checklist: strike through an ingredient once it's checked off.
// Purely a visual aid while cooking - nothing is saved, so refreshing the
// page resets it.
(function () {
  document.querySelectorAll("[data-ingredient-checklist] input[type='checkbox']").forEach(function (checkbox) {
    checkbox.addEventListener("change", function () {
      const item = checkbox.closest("li");
      if (item) {
        item.classList.toggle("checked", checkbox.checked);
      }
    });
  });
})();