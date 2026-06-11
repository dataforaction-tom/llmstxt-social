import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import SurfaceSwitch from './SurfaceSwitch';
import { useEditorSurface } from './useEditorSurface';

describe('useEditorSurface', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('defaults to guided when no value is set', () => {
    function Probe() {
      const [s] = useEditorSurface('profile');
      return <span>{s}</span>;
    }
    render(<Probe />);
    expect(screen.getByText('guided')).toBeInTheDocument();
  });

  it('persists per record kind and reads on remount', () => {
    function Probe({ kind }: { kind: 'profile' | 'strategy' }) {
      const [s, setS] = useEditorSurface(kind);
      return (
        <div>
          <span data-testid="val">{s}</span>
          <button type="button" onClick={() => setS('markdown')}>set md</button>
        </div>
      );
    }
    const { unmount, getByTestId, getByRole } = render(<Probe kind="profile" />);
    fireEvent.click(getByRole('button', { name: /set md/i }));
    expect(getByTestId('val').textContent).toBe('markdown');
    unmount();

    // Strategy is still default-guided.
    const s = render(<Probe kind="strategy" />);
    expect(s.getByTestId('val').textContent).toBe('guided');
    s.unmount();

    // Profile remembers markdown.
    const p = render(<Probe kind="profile" />);
    expect(p.getByTestId('val').textContent).toBe('markdown');
  });
});

describe('SurfaceSwitch', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('renders both options and calls onChange', () => {
    const onChange = vi.fn();
    render(<SurfaceSwitch value="guided" onChange={onChange} />);
    fireEvent.click(screen.getByRole('button', { name: /markdown/i }));
    expect(onChange).toHaveBeenCalledWith('markdown');
  });
});
