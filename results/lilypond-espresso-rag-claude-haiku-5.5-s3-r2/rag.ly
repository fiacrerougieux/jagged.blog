\version "2.24.1"

\header {
  title = "Espresso Rag"
  subtitle = "for café piano"
  composer = "Anon."
  tagline = ##f
}

% Bars 1-8: right hand on top staff (treble), left hand on bottom (bass).
% Bars 9-12: hands cross. Right hand moves down to the bass staff,
%            left hand moves up to the treble staff.
% Bars 13-16: hands return to their home staves.

rhHome = {
  e'8 g' c'' g' e' g' c'' g' |
  d''4 c''8 a' g' e' f'4 |
  c''8 g' e'' c'' g''4 e''4 |
  e'8 g' c'' e'' g''2 |
  a''8 g'' f'' e'' d''4 c''4 |
  b'4 g'8 d'' c''4 e'4 |
  f'8 a' c'' f'' e''4 d''4 |
  c''2 e''4 g'4 |
}
rhCross = {
  c4 e8 g8 c'4 g4 |
  d4 f8 a8 f4 d4 |
  c4 e8 g8 c'4 g4 |
  e4 g8 b8 g4 d4 |
}
rhReturn = {
  g'4 c''8 d'' e''4 g''4 |
  f''2 e''4 d''4 |
  c''8 e'' g'' c''' b''4 g''4 |
  c''1 |
}

lhHome = {
  c4 <g c'>4 c4 <g c'>4 |
  f,4 <c f>4 f,4 <c f>4 |
  g,4 <d g>4 g,4 <d g>4 |
  c4 <g c'>4 c4 <g c'>4 |
  a,4 <e a>4 a,4 <e a>4 |
  d,4 <a, d>4 d,4 <a, d>4 |
  g,4 <d g>4 g,4 <d g>4 |
  c4 <g c'>4 c4 <g c'>4 |
}
lhCross = {
  <g c' e'>2 <g c' e'>2 |
  <a c' f'>2 <a c' f'>2 |
  <g b d'>2 <g c' e'>2 |
  <g c' e'>1 |
}
lhReturn = {
  c,4 <g, c>4 c4 <g c>4 |
  d,4 <a, d>4 g,4 <d g>4 |
  c,4 <g, c>4 c4 <g c>4 |
  <c, g, c>1 |
}

rhMusic = {
  \rhHome
  \change Staff = "down"
  \rhCross
  \change Staff = "up"
  \rhReturn
}
lhMusic = {
  \lhHome
  \change Staff = "up"
  \lhCross
  \change Staff = "down"
  \lhReturn
}

\score {
  \new PianoStaff <<
    \new Staff = "up" <<
      \clef treble
      \key c \major
      \time 4/4
      \tempo "Allegro" 4 = 132
      \context Voice = "R" { \voiceOne \rhMusic }
    >>
    \new Staff = "down" <<
      \clef bass
      \key c \major
      \time 4/4
      \context Voice = "L" { \voiceTwo \lhMusic }
    >>
  >>
  \layout { }
}
