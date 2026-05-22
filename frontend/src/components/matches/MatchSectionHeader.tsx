import { hdrClass } from '../../utils/labels';

interface Props {
  label: string;
  count: number;
  emoji: string;
}

export default function MatchSectionHeader({ label, count, emoji }: Props) {
  return (
    <div className={`section-hdr ${hdrClass(label)}`}>
      {emoji} {label.toUpperCase()} <span className="sh-n">{count}</span>
    </div>
  );
}
