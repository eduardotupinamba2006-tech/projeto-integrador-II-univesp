// Distância e ordenação de paróquias por proximidade.

const RAIO_TERRA_KM = 6371;

export function distanciaKm(a, b) {
  const rad = (g) => (g * Math.PI) / 180;
  const dLat = rad(b.lat - a.lat);
  const dLng = rad(b.lng - a.lng);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLng / 2) ** 2;
  return 2 * RAIO_TERRA_KM * Math.asin(Math.sqrt(h));
}

// Paróquias com coordenadas vêm primeiro, da mais próxima para a mais distante;
// as sem coordenadas vão para o fim, em ordem alfabética.
export function ordenarPorProximidade(paroquias, origem) {
  const comDistancia = paroquias.map((p) => {
    const temCoordenada = p.lat != null && p.lng != null;
    return {
      ...p,
      distanciaKm: temCoordenada ? distanciaKm(origem, { lat: Number(p.lat), lng: Number(p.lng) }) : null,
    };
  });
  return comDistancia.sort((a, b) => {
    if (a.distanciaKm == null && b.distanciaKm == null) return a.nome.localeCompare(b.nome, 'pt-BR');
    if (a.distanciaKm == null) return 1;
    if (b.distanciaKm == null) return -1;
    return a.distanciaKm - b.distanciaKm;
  });
}

export function formatarDistancia(km) {
  if (km == null) return '';
  return km < 1 ? `${Math.round(km * 1000)} m` : `${km.toFixed(1).replace('.', ',')} km`;
}

export function filtrarPorNome(paroquias, termo) {
  const normalizar = (t) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const alvo = normalizar(String(termo ?? '').trim());
  if (!alvo) return paroquias;
  return paroquias.filter((p) => normalizar(`${p.nome} ${p.endereco}`).includes(alvo));
}
