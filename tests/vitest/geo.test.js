import { describe, expect, it } from 'vitest';
import { distanciaKm, filtrarPorNome, formatarDistancia, ordenarPorProximidade } from '../../js/lib/geo.js';

const SE = { lat: -23.55052, lng: -46.633308 };
const PINHEIROS = { lat: -23.5672, lng: -46.6927 };
const BH = { lat: -19.916681, lng: -43.934493 };

const paroquias = [
  { id: 'bh', nome: 'Paróquia Nossa Senhora do Teste', endereco: 'Belo Horizonte/MG', ...BH },
  { id: 'sem', nome: 'Paróquia Sem Coordenada', endereco: 'Rua X', lat: null, lng: null },
  { id: 'pin', nome: 'Paróquia Santa Amostra', endereco: 'Pinheiros, São Paulo/SP', ...PINHEIROS },
  { id: 'se', nome: 'Paróquia São Exemplo', endereco: 'Centro, São Paulo/SP', ...SE },
];

describe('distanciaKm', () => {
  it('é zero para o mesmo ponto e simétrica', () => {
    expect(distanciaKm(SE, SE)).toBe(0);
    expect(distanciaKm(SE, BH)).toBeCloseTo(distanciaKm(BH, SE), 6);
  });

  it('calcula distâncias conhecidas com boa aproximação', () => {
    expect(distanciaKm(SE, PINHEIROS)).toBeGreaterThan(6);
    expect(distanciaKm(SE, PINHEIROS)).toBeLessThan(7);
    expect(distanciaKm(SE, BH)).toBeGreaterThan(480);
    expect(distanciaKm(SE, BH)).toBeLessThan(500);
  });
});

describe('ordenarPorProximidade', () => {
  it('ordena da mais próxima para a mais distante e deixa sem coordenada no fim', () => {
    const ordem = ordenarPorProximidade(paroquias, { lat: -23.551, lng: -46.634 }).map((p) => p.id);
    expect(ordem).toEqual(['se', 'pin', 'bh', 'sem']);
  });

  it('não altera a lista original', () => {
    const copia = JSON.stringify(paroquias);
    ordenarPorProximidade(paroquias, SE);
    expect(JSON.stringify(paroquias)).toBe(copia);
  });
});

describe('filtrarPorNome e formatarDistancia', () => {
  it('filtra por nome ou endereço ignorando acentos e maiúsculas', () => {
    expect(filtrarPorNome(paroquias, 'sao exemplo').map((p) => p.id)).toEqual(['se']);
    expect(filtrarPorNome(paroquias, 'PINHEIROS').map((p) => p.id)).toEqual(['pin']);
    expect(filtrarPorNome(paroquias, '  ')).toHaveLength(4);
  });

  it('mostra metros abaixo de 1 km', () => {
    expect(formatarDistancia(0.35)).toBe('350 m');
    expect(formatarDistancia(6.43)).toBe('6,4 km');
    expect(formatarDistancia(null)).toBe('');
  });
});
