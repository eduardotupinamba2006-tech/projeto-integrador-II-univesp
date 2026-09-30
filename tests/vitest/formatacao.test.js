import { describe, expect, it } from 'vitest';
import { escaparHtml, formatarData, formatarMoeda } from '../../js/lib/formatacao.js';

describe('formatação', () => {
  it('formata moeda em reais', () => {
    expect(formatarMoeda(30)).toBe('R$ 30,00');
    expect(formatarMoeda('1234.5')).toBe('R$ 1.234,50');
    expect(formatarMoeda(null)).toBe('R$ 0,00');
  });

  it('formata data ISO sem deslocar o dia pelo fuso', () => {
    expect(formatarData('1995-03-12')).toBe('12/03/1995');
    expect(formatarData('2026-01-01T00:00:00+00:00')).toBe('01/01/2026');
    expect(formatarData(null)).toBe('');
  });

  it('escapa HTML de texto digitado por usuários', () => {
    expect(escaparHtml('<img src=x onerror="a">')).toBe('&lt;img src=x onerror=&quot;a&quot;&gt;');
  });
});
