import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useAutosave } from './useAutosave';

describe('useAutosave', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('debounces saves by 600ms', async () => {
    const save = vi.fn(async () => undefined);
    const { rerender } = renderHook(({ source }) => useAutosave(source, save), {
      initialProps: { source: 'a' },
    });
    rerender({ source: 'b' });
    rerender({ source: 'c' });
    expect(save).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(599);
    });
    expect(save).not.toHaveBeenCalled();
    await act(async () => {
      vi.advanceTimersByTime(2);
    });
    expect(save).toHaveBeenCalledTimes(1);
    expect(save).toHaveBeenCalledWith('c');
  });

  it('sets state to saving then saved on success', async () => {
    let resolve: (() => void) | null = null;
    const save = vi.fn(
      () =>
        new Promise<void>((r) => {
          resolve = () => r();
        }),
    );
    const { result, rerender } = renderHook(({ source }) => useAutosave(source, save), {
      initialProps: { source: 'a' },
    });
    rerender({ source: 'b' });
    await act(async () => {
      vi.advanceTimersByTime(601);
    });
    expect(result.current.state).toBe('saving');
    await act(async () => {
      resolve!();
    });
    expect(result.current.state).toBe('saved');
    expect(result.current.savedAt).toBeInstanceOf(Date);
  });

  it('flips to error and exposes retry', async () => {
    let reject: ((e: Error) => void) | null = null;
    const save = vi
      .fn()
      .mockImplementationOnce(
        () =>
          new Promise<void>((_, r) => {
            reject = (e) => r(e);
          }),
      )
      .mockResolvedValueOnce(undefined);
    const { result, rerender } = renderHook(({ source }) => useAutosave(source, save), {
      initialProps: { source: 'a' },
    });
    rerender({ source: 'b' });
    await act(async () => {
      vi.advanceTimersByTime(601);
    });
    await act(async () => {
      reject!(new Error('boom'));
    });
    expect(result.current.state).toBe('error');
    await act(async () => {
      result.current.retry();
    });
    expect(save).toHaveBeenCalledTimes(2);
  });
});
