import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import GroupRule from './GroupRule';

describe('GroupRule', () => {
  it('renders the caption and children', () => {
    render(
      <GroupRule caption="Place">
        <div>child A</div>
        <div>child B</div>
      </GroupRule>,
    );
    expect(screen.getByText('Place')).toBeInTheDocument();
    expect(screen.getByText('child A')).toBeInTheDocument();
    expect(screen.getByText('child B')).toBeInTheDocument();
  });

  it('renders a dashed top border on the wrapper', () => {
    const { container } = render(
      <GroupRule caption="Place">
        <span />
      </GroupRule>,
    );
    const wrap = container.firstElementChild as HTMLElement;
    expect(wrap.className).toMatch(/border-dashed/);
  });
});
