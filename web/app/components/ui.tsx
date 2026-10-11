import type { ComponentPropsWithRef, ElementType, HTMLAttributes } from 'react';

export const cx = (...parts: Array<string | false | null | undefined>) => parts.filter(Boolean).join(' ');

/* ------------------------------------------------------------------ Panel */

type PanelTone = 'plate' | 'dialog' | 'well';

interface PanelProps extends HTMLAttributes<HTMLElement> {
  tone?: PanelTone;
  flat?: boolean;
  as?: ElementType;
}

/** The one surface. plate = cream/slate (information), dialog = navy/gold (choices), well = recessed field. */
export function Panel({ tone = 'plate', flat, as: Tag = 'div', className, children, ...rest }: PanelProps) {
  return (
    <Tag className={cx('panel', `panel-${tone}`, (flat || tone === 'well') && 'panel-flat', className)} {...rest}>
      {children}
    </Tag>
  );
}

/* ----------------------------------------------------------------- Buttons */

type Variant = 'primary' | 'secondary' | 'quiet';
const variantClass: Record<Variant, string> = { primary: '', secondary: 'btn-secondary', quiet: 'btn-quiet' };

interface ButtonProps extends ComponentPropsWithRef<'button'> {
  variant?: Variant;
  small?: boolean;
  icon?: boolean;
}

export function Button({ variant = 'primary', small, icon, className, type = 'button', ...rest }: ButtonProps) {
  return <button type={type} className={cx('btn', variantClass[variant], small && 'btn-sm', icon && 'btn-icon', className)} {...rest} />;
}

/* ------------------------------------------------------------------- Chips */

export type Elem = 'electric' | 'fire' | 'grass' | 'water' | 'psychic' | 'normal' | 'ghost' | 'dark' | 'flying';

export const Chip = ({ kind = 'plain', className, children }: { kind?: Elem | 'plain' | 'bull' | 'bear' | 'flat'; className?: string; children: React.ReactNode }) => (
  <span className={cx('chip', `chip-${kind}`, className)}>{children}</span>
);

/** Shape + word + colour so state never rests on colour alone. */
export function StatusChip({ status }: { status: 'idle' | 'working' | 'thinking' | 'error' | 'asleep' }) {
  const m = {
    idle: ['■', 'chip-flat'],
    asleep: ['z', 'chip-flat'],
    working: ['▶', 'chip-water'],
    thinking: ['…', 'chip-electric'],
    error: ['!', 'chip-bear'],
  }[status];
  return (
    <span className={cx('chip', m[1])}>
      <span aria-hidden="true">{m[0]}</span>
      {status}
    </span>
  );
}

/* ---------------------------------------------------------------- Stat bar */

export function StatBar({ label, value, max, color, display }: { label: string; value: number; max: number; color?: string; display?: string }) {
  const pct = Math.max(3, Math.min(100, Math.round((value / max) * 100)));
  return (
    <div className="grid grid-cols-[4.4rem_1fr_3.2rem] items-center gap-2">
      <span className="font-pixel t-8 text-slate">{label}</span>
      <div className="bar" role="presentation">
        <i style={{ width: `${pct}%`, ['--bar' as string]: color }} />
      </div>
      <span className="font-pixel t-8 text-right tabular-nums">{display ?? value}</span>
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={cx('spinner', className)} aria-hidden="true" />;
}
