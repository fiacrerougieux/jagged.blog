\version "2.24.0"

\header {
  title = "Espresso Rag"
  subtitle = "for café piano"
  tagline = ##f
}

% Right hand starts in the treble staff, left hand in the bass staff.
% In bars 9-12 the hands cross: the LH (now higher) moves to the treble
% staff and the RH (now lower) moves to the bass staff. Switches happen
% at barlines with \change Staff.

rhMusic = {
  % bars 1-8: RH in treble
  e'8 g' c'' g' e'4 c'4 |
  d'8 g' b' g' d'4 g'4 |
  c'8 f' a' f' c'4 f'4 |
  c'8 e' a' e' c'4 e'4 |
  d'8 g' b' g' d'4 f'4 |
  c'8 e' g' e' c'4 e'4 |
  b8 d' g' d' b4 d'4 |
  <c' e' g'>1 |
  % bars 9-12: RH crosses down to bass staff
  \change Staff = "lower"
  c2 g2 | f2 c'2 | g2 d'2 | c1 |
  % bars 13-16: RH back to treble
  \change Staff = "upper"
  e'8 g' c'' g' e'4 c'4 |
  f'8 a' c'' a' f'4 c'4 |
  d'8 g' b' g' d'4 g'4 |
  <c' e' g'>1 \fermata \bar "|."
}

lhMusic = {
  % bars 1-8: LH in bass
  c,4 g,4 c4 g,4 |
  g,4 d4 g4 d4 |
  f,4 c4 f4 c4 |
  f,4 c4 a,4 c4 |
  g,4 d4 g4 d4 |
  c,4 g,4 c4 g,4 |
  g,4 d4 g4 d4 |
  c,1 |
  % bars 9-12: LH crosses up to treble staff, playing above the RH
  \change Staff = "upper"
  g''8 e'' c'' e'' g''4 c'''4 |
  a''8 f'' c'' f'' a''4 c'''4 |
  b''8 g'' d'' g'' b''4 d'''4 |
  c'''8 g'' e'' g'' c'''4 g''4 |
  % bars 13-16: LH back to bass
  \change Staff = "lower"
  c,4 g,4 c4 g,4 |
  f,4 c4 f4 c4 |
  g,4 d4 g4 d4 |
  c,1 \fermata
}

\score {
  \new PianoStaff <<
    \new Staff = "upper" <<
      \tempo "Allegro" 4 = 116
      \clef treble
      \key c \major
      \time 4/4
      \new Voice = "rh" { \rhMusic }
    >>
    \new Staff = "lower" <<
      \clef bass
      \key c \major
      \time 4/4
      \new Voice = "lh" { \lhMusic }
    >>
  >>
  \layout { }
}
