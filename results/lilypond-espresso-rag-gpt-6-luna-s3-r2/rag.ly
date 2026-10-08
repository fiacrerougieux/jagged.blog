\version "2.24.0"

\header {
  title = "Espresso Rag"
  subtitle = "A little café piano two-step"
  composer = ""
}

rightHand = {
  \clef treble
  \key c \major
  \time 2/4
  \tempo "Bright, with a bounce" 4 = 126
  \voiceOne
  c''8 e''8 g''8 e''8 |
  d''8 f''8 b''8 f''8 |
  c''8 e''8 g''8 c'''8 |
  b''8 a''8 g''8 d''8 |
  a'8 c''8 f''8 c''8 |
  a'8 c''8 f''8 a''8 |
  g'8 c''8 e''8 g''8 |
  d''8 f''8 b''8 d'''8 |
  \mark \markup { \box \small "L.H. crosses over R.H." }
  <c' e'>8 r8 <d' f'>8 r8 |
  <b d'>8 r8 <c' e'>8 r8 |
  <a c'>8 r8 <d' f'>8 r8 |
  <g b>8 r8 <c' e'>8 r8 |
  c''8 e''8 g''8 e''8 |
  d''8 f''8 a''8 f''8 |
  g'8 c''8 e''8 g''8 |
  <c' e' g'>4 <c' e' g'>4
  \bar "|."
}

leftHand = {
  \clef bass
  \key c \major
  \time 2/4
  \voiceTwo
  <c, c>4 <e g c'>4 |
  <g, g>4 <d' f' b'>4 |
  <c, c>4 <e g c'>4 |
  <g, g>4 <d' f' b'>4 |
  <f, f>4 <a c' f'>4 |
  <f, f>4 <a c' f'>4 |
  <c, c>4 <e g c'>4 |
  <g, g>4 <d' f' b'>4 |
  \change Staff = "upper"
  <c'' e'' g''>4 <g' c'' e''>4 |
  <d'' f'' a''>4 <a' d'' f''>4 |
  <e'' g'' c'''>4 <g'' c''' e'''>4 |
  <d'' f'' b''>4 <g' b' d''>4 |
  \change Staff = "lower"
  <c, c>4 <e g c'>4 |
  <g, g>4 <d' f' b'>4 |
  <c, c>4 <e g c'>4 |
  <c, c>4 <e g c'>4
  \bar "|."
}

\score {
  \new PianoStaff \with { instrumentName = "Piano" } <<
    \new Staff = "upper" \rightHand
    \new Staff = "lower" \leftHand
  >>
  \layout {
    \context { \PianoStaff \consists #Span_stem_engraver }
  }
}
