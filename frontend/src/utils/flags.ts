/**
 * Country-code to flag-emoji map.
 * Ported from the vanilla JS `FL` constant.
 */
const FL: Record<string, string> = {
  ARG: '🇦🇷', MEX: '🇲🇽', BRA: '🇧🇷', FRA: '🇫🇷', GER: '🇩🇪', ESP: '🇪🇸',
  ENG: '🏴󠁧󠁢󠁥󠁮󠁧󠁿', POR: '🇵🇹', NED: '🇳🇱', URU: '🇺🇾', COL: '🇨🇴', MAR: '🇲🇦',
  USA: '🇺🇸', CRO: '🇭🇷', SUI: '🇨🇭', BEL: '🇧🇪', JPN: '🇯🇵', KOR: '🇰🇷',
  AUS: '🇦🇺', CAN: '🇨🇦', ECU: '🇪🇨', SEN: '🇸🇳', GHA: '🇬🇭', NGA: '🇳🇬',
  CMR: '🇨🇲', CIV: '🇨🇮', EGY: '🇪🇬', RSA: '🇿🇦', ALG: '🇩🇿', QAT: '🇶🇦',
  KSA: '🇸🇦', IRN: '🇮🇷', JOR: '🇯🇴', IRQ: '🇮🇶', NZL: '🇳🇿', PAN: '🇵🇦',
  HAI: '🇭🇹', CUR: '🇨🇼', PAR: '🇵🇾', NOR: '🇳🇴', SCO: '🏴󠁧󠁢󠁳󠁣󠁴󠁿', SRB: '🇷🇸',
  TUR: '🇹🇷', AUT: '🇦🇹', SWE: '🇸🇪', CZE: '🇨🇿', BIH: '🇧🇦', POL: '🇵🇱',
  UZB: '🇺🇿', CPV: '🇨🇻', COD: '🇨🇩', DEN: '🇩🇰',
};

/** Return the flag emoji for a FIFA country code, or a white flag as fallback. */
export function fl(code: string): string {
  return FL[code] ?? '🏳️';
}

export default FL;
