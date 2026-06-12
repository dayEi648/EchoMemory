import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface CarouselSlide {
  title: string;
  subtitle: string;
  /** CSS gradient string, e.g. "linear-gradient(135deg, #1a3a3a, #2d5a5a)" */
  gradient: string;
  /** Optional action button label, not implemented yet */
  actionLabel?: string;
}

interface HeroCarouselProps {
  slides: CarouselSlide[];
  /** Auto-rotate interval in ms, default 5000 */
  interval?: number;
}

export const HeroCarousel = ({ slides, interval = 5000 }: HeroCarouselProps) => {
  const [current, setCurrent] = useState(0);
  const [direction, setDirection] = useState(1);

  const goTo = useCallback(
    (index: number) => {
      setDirection(index > current ? 1 : -1);
      setCurrent(index);
    },
    [current],
  );

  const next = useCallback(() => {
    setDirection(1);
    setCurrent((prev) => (prev + 1) % slides.length);
  }, [slides.length]);

  const prev = useCallback(() => {
    setDirection(-1);
    setCurrent((prev) => (prev - 1 + slides.length) % slides.length);
  }, [slides.length]);

  // auto-rotate
  useEffect(() => {
    if (slides.length <= 1) return;
    const timer = setInterval(next, interval);
    return () => clearInterval(timer);
  }, [next, interval, slides.length]);

  if (slides.length === 0) return null;

  const slide = slides[current];

  return (
    <div className="hero-carousel">
      <div className="hero-carousel-track">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={current}
            className="hero-carousel-slide"
            style={{ background: slide.gradient }}
            custom={direction}
            initial={{ opacity: 0, x: direction * 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction * -40 }}
            transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
          >
            <div className="hero-carousel-content">
              <h2 className="hero-carousel-title">{slide.title}</h2>
              <p className="hero-carousel-subtitle">{slide.subtitle}</p>
              {slide.actionLabel && (
                <button type="button" className="hero-carousel-action">
                  {slide.actionLabel}
                </button>
              )}
            </div>
            {/* decorative circles */}
            <div className="hero-carousel-deco">
              <div className="hero-carousel-deco-circle" style={{ width: 260, height: 260, top: "-15%", right: "10%" }} />
              <div className="hero-carousel-deco-circle" style={{ width: 180, height: 180, bottom: "-20%", left: "8%" }} />
            </div>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* arrows */}
      {slides.length > 1 && (
        <>
          <motion.button
            type="button"
            className="hero-carousel-arrow hero-carousel-arrow--left"
            onClick={prev}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            <ChevronLeft size={20} />
          </motion.button>
          <motion.button
            type="button"
            className="hero-carousel-arrow hero-carousel-arrow--right"
            onClick={next}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
          >
            <ChevronRight size={20} />
          </motion.button>
        </>
      )}

      {/* dots */}
      {slides.length > 1 && (
        <div className="hero-carousel-dots">
          {slides.map((_, i) => (
            <button
              key={i}
              type="button"
              className={`hero-carousel-dot${i === current ? " active" : ""}`}
              onClick={() => goTo(i)}
              aria-label={`切换到第 ${i + 1} 张`}
            />
          ))}
        </div>
      )}
    </div>
  );
};
