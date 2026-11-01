import LatticeLoader from "./LatticeLoader";

// One loading look for every wait in the app: a small orbiting lattice and the word "Loading".
// `compact` is for waits inside a panel; the default centres in the page.
export default function PageLoader({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-center justify-center text-fg2 ${compact ? "py-4" : "min-h-[40vh] py-10"}`}>
      <LatticeLoader
        label="Loading" showTimer={false} pattern="orbit" grid={3} shape="round"
        cellSize={compact ? 5 : 8} gap={compact ? 2 : 3} fontSize={compact ? 13 : 15} idleOpacity={0.18}
      />
    </div>
  );
}
