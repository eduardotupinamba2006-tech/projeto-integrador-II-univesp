import { describe, expect, it } from 'vitest';
import {
  formatarCPF, normalizarValor, validarCPF, validarEmail, validarMotivo, validarSenha,
} from '../../js/lib/validacao.js';

describe('validarCPF', () => {
  it('aceita CPF com dígitos verificadores corretos, com ou sem máscara', () => {
    // CPFs gerados só para teste (dígitos válidos, não pertencem a ninguém conhecido).
    expect(validarCPF('529.982.247-25')).toBe(true);
    expect(validarCPF('52998224725')).toBe(true);
  });

  it('recusa dígito verificador errado, sequência repetida e tamanho inválido', () => {
    expect(validarCPF('529.982.247-26')).toBe(false);
    expect(validarCPF('111.111.111-11')).toBe(false);
    expect(validarCPF('1234')).toBe(false);
    expect(validarCPF('')).toBe(false);
    expect(validarCPF(null)).toBe(false);
  });
});

describe('formatarCPF', () => {
  it('aplica a máscara enquanto a pessoa digita', () => {
    expect(formatarCPF('529')).toBe('529');
    expect(formatarCPF('5299822')).toBe('529.982.2');
    expect(formatarCPF('52998224725')).toBe('529.982.247-25');
    expect(formatarCPF('529982247259999')).toBe('529.982.247-25');
  });
});

describe('validarEmail e validarSenha', () => {
  it('valida formato de email', () => {
    expect(validarEmail('fiel@teste.local')).toBe(true);
    expect(validarEmail(' fiel@teste.local ')).toBe(true);
    expect(validarEmail('fiel@')).toBe(false);
    expect(validarEmail('sem arroba')).toBe(false);
  });

  it('exige senha com pelo menos 8 caracteres', () => {
    expect(validarSenha('12345678')).toBe(true);
    expect(validarSenha('1234567')).toBe(false);
    expect(validarSenha(undefined)).toBe(false);
  });
});

describe('normalizarValor (dízimo)', () => {
  it.each([
    ['50', '50.00'],
    ['50,5', '50.50'],
    ['1.234,56', '1234.56'],
    ['R$ 10,00', '10.00'],
    ['99.90', '99.90'],
    ['1', '1.00'],
    ['100000', '100000.00'],
  ])('%s -> %s', (entrada, esperado) => {
    expect(normalizarValor(entrada)).toBe(esperado);
  });

  it.each(['', '0', '0,99', '-5', 'abc', '10,001', '100000,01', null])('recusa %s', (entrada) => {
    expect(normalizarValor(entrada)).toBeNull();
  });
});

describe('validarMotivo', () => {
  it('exige texto não vazio para rejeitar', () => {
    expect(validarMotivo('Registro não localizado no livro 12')).toBe(true);
    expect(validarMotivo('   ')).toBe(false);
    expect(validarMotivo(null)).toBe(false);
  });
});
