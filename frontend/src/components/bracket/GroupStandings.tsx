import type { GroupStanding } from '../../types';
import { fl } from '../../utils/flags';

interface Props {
  standings: GroupStanding[];
}

export default function GroupStandings({ standings }: Props) {
  return (
    <>
      <div className="bracket-section-title">Fase de Grupos</div>
      <div className="group-grid">
        {standings.map((grp) => (
          <div className="group-card" key={grp.group}>
            <div className="gc-hdr">Grupo {grp.group}</div>
            {grp.teams.map((t) => {
              const cls = t.qualified
                ? 'qua'
                : t.third_place
                  ? 'thi'
                  : 'eli';
              const adv = t.qualified ? '\u2713' : t.third_place ? '*' : '';
              return (
                <div className={`gc-row ${cls}`} key={t.team}>
                  <span>
                    {fl(t.team)} {t.team}
                  </span>
                  <span className="gc-pts">{t.pts}pts</span>
                  <span className="gc-adv">{adv}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
    </>
  );
}
