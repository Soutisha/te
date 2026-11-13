import { animate, inView, stagger } from "motion";

const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
if (!reducedMotion) {
  const ease = [0.22, 1, 0.36, 1];
  const heroItems = document.querySelectorAll(".hero .hero-content > *");
  if (heroItems.length) {
    animate(
      heroItems,
      { opacity: [0, 1], y: [18, 0] },
      { duration: 0.72, delay: stagger(0.09), ease }
    );
  }

  inView(".stats", (element) => {
    animate(
      element.querySelectorAll(".stat"),
      { opacity: [0, 1], y: [18, 0] },
      { duration: 0.5, delay: stagger(0.08), ease }
    );
  }, { once: true, amount: 0.18 });

  inView(".section", (element) => {
    const cards = element.querySelectorAll(".card, .tool-card");
    if (cards.length) {
      animate(
        cards,
        { opacity: [0, 1], y: [20, 0] },
        { duration: 0.52, delay: stagger(0.055), ease }
      );
    } else {
      animate(element, { opacity: [0, 1], y: [16, 0] }, { duration: 0.5, ease });
    }
  }, { once: true, amount: 0.08 });

  inView(".main > .top, .main > .auth-bar, .main > .alert, .main > .card", (element) => {
    animate(element, { opacity: [0, 1], y: [14, 0] }, { duration: 0.48, ease });
  }, { once: true, amount: 0.12 });
}
