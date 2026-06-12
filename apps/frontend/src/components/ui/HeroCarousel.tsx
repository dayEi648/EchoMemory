import { useState, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ChevronLeft, ChevronRight } from "lucide-react";

export interface CarouselSlide {
  title: string;
  subtitle: string;
  /** CSS gradient string (fallback when no image) */
  gradient: string;
  /** Background image URL */
  imageUrl?: string | null;
  /** Click handler */
  onClick?: () => void;
}

interface HeroCarouselProps {
  slides: CarouselSlide[];
  /** Auto-rotate interval in ms, default 5000 */
  interval?: number;
}

/** 预定义的品牌渐变色列表，用于无封面图时的回退 */
const FALLBACK_GRADIENTS = [
  "linear-gradient(135deg, #1a3a3a 0%, #2d5a5a 60%, #3a6a6a 100%)",
  "linear-gradient(135deg, #4a1a3a 0%, #7a2d5a 60%, #9a4a7a 100%)",
  "linear-gradient(135deg, #1a2a4a 0%, #2d3a7a 60%, #4a5a9a 100%)",
];

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
  const fallbackGradient = slide.gradient || FALLBACK_GRADIENTS[current % FALLBACK_GRADIENTS.length];

  return (
    <div className="hero-carousel">
      <div className="hero-carousel-track">
        <AnimatePresence mode="wait" custom={direction}>
          <motion.div
            key={current}
            className="hero-carousel-slide"
            style={{ background: fallbackGradient }}
            custom={direction}
            initial={{ opacity: 0, x: direction * 40 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: direction * -40 }}
            transition={{ duration: 0.4, ease: [0.25, 0.1, 0.25, 1] }}
            onClick={slide.onClick}
            role={slide.onClick ? "button" : undefined}
            tabIndex={slide.onClick ? 0 : undefined}
            onKeyDown={(e) => {
              if (slide.onClick && (e.key === "Enter" || e.key === " ")) {
                e.preventDefault();
                slide.onClick();
              }
            }}
          >
            {/* 背景图片 */}
            {slide.imageUrl && (
              <div
                className="hero-carousel-bg-img"
                style={{ backgroundImage: `url(${slide.imageUrl})` }}
              />
            )}
            <div className="hero-carousel-content">
              <h2 className="hero-carousel-title">{slide.title}</h2>
              <p className="hero-carousel-subtitle">{slide.subtitle}</p>
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
