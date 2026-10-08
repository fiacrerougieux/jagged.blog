\version "2.24.1"

\header {
  title = "Espresso Rag"
  subtitle = "A little café two-step"
  composer = "For solo piano"
  tagline = ##f
}

\paper {
  #(set-paper-size "a4")
  top-margin = 12\mm
  bottom-margin = 12\mm
  system-system-spacing.basic-distance = #19
}

rightHand = {
  \clef treble \key c \major \time 2/4
  \tempo "Lightly, with a wink" 4 = 112
  \override Score.RehearsalMark.self-alignment-X = #LEFT
  % 1–4: a jaunty, syncopated opening.
  e''8\mf-.( g''8~ g''8 e''8) |
  cis''8-.( e''8~ e''8 a''8) |
  f''8-.( a''8~ a''8 f''8) |
  d''8-. b'16( c''16) d''8-. g'8-. | \break
  % 5–8: answer, with a chromatic coffee-house turn.
  e''8-.( g''8~ g''8 c'''8) |
  b''8-. gis''16( a''16) b''8-. e''8-. |
  c''8( e''8) fis''8( a''8) |
  g''8-. f''16( e''16) d''8-. b'8-. | \break
  % 9–12: right hand stays low; left hand plays ABOVE it.
  \voiceTwo
  <e' g'>8\mp-. <e' g'>4-> <e' g'>8-. |
  <cis' g'>8-. <cis' g'>4-> <cis' g'>8-. |
  <d' f'>8-. <d' f'>4-> <d' f'>8-. |
  <d' f'>8-. <b f'>4-> <b f'>8-. | \break
  % 13–16: return to the opening texture and close.
  \oneVoice
  e''8\mf-.( g''8~ g''8 e''8) |
  cis''8-.( e''8~ e''8 a''8) |
  f''8( a''8) g''8( b''8) |
  <e'' g'' c'''>8-> r8 <e' g' c''>4-.\fermata \bar "|."
}

leftHand = {
  \clef bass \key c \major \time 2/4
  c8-. <e g>8-. g,8-. <e g>8-. |
  a,8-. <g cis' e'>8-. e8-. <g cis' e'>8-. |
  d8-. <f a>8-. a,8-. <f a>8-. |
  g,8-. <f b>8-. d8-. <f b>8-. |
  c8-. <e g>8-. g,8-. <e g>8-. |
  e,8-. <gis b d'>8-. b,8-. <gis b d'>8-. |
  a,8-. <c' e'>8-. d8-. <fis c'>8-. |
  g,8-. <f b>8-. g8-. <f b>8-. |
  \change Staff = "upper" \voiceOne \dynamicUp
  e''8\p-.[^\markup { \bold "L.H. over R.H. — bars 9–12" } g''8-.] c'''8-.[ g''8-.] |
  e''8-.[ g''8-.] a''8-.[ cis'''8-.] |
  f''8-.[ a''8-.] d'''8-.[ a''8-.] |
  g''8-.[ b''8-.] d'''8-.[ b''8-.] |
  \change Staff = "lower" \oneVoice \dynamicNeutral
  c8-._\markup { \italic "Hands return" } <e g>8-. g,8-. <e g>8-. |
  a,8-. <g cis' e'>8-. e8-. <g cis' e'>8-. |
  d8-. <f a>8-. g,8-. <f b>8-. |
  <c g>8-> r8 <c, c>4-.\fermata
}

\score {
  \new PianoStaff \with { instrumentName = "Piano" } <<
    \new Staff = "upper" \new Voice = "right" { \rightHand }
    \new Staff = "lower" \new Voice = "left" { \leftHand }
  >>
  \layout {
    indent = 12\mm
    \context {
      \Score
      barNumberVisibility = #all-bar-numbers-visible
      \override BarNumber.break-visibility = #begin-of-line-visible
    }
  }
  \midi { }
}
