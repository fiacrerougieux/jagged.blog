\version "2.24.1"

\header {
  title = "Espresso Rag"
  subtitle = "A little café rag for piano"
  composer = ""
  tagline = ##f
}

\paper {
  #(set-paper-size "a4")
  indent = 12\mm
  top-margin = 12\mm
  bottom-margin = 12\mm
  system-system-spacing.basic-distance = #18
}

common = { \key c \major \time 2/4 }

rightHand = \relative c'' {
  \common
  \tempo "Lightly, with a café bounce" 4 = 108
  \clef treble
  % 1–4: a clipped, syncopated opening phrase.
  e8\mf g16 a~ a8 g |
  e16 g e c~ c8 e |
  f8 a16 c~ c8 a |
  g16 e d c~ c8 r | \break
  % 5–8: answer, turning back toward C.
  e8 g16 a~ a8 c |
  b16 a gis a~ a8 e |
  f16 a f d~ d8 fis |
  g8 b16 d~ d8 r | \break
  % 9–12: R.H. stays BELOW the crossing left hand.
  \voiceTwo
  <c,, e g>8-\markup { \italic "R.H. (below)" } r
    <c e g>8 r |
  <c f a>8 r <c f a>8 r |
  <d f a>8 r <d fis a>8 r |
  <d g b>8 r <d f b>8 r | \break
  % 13–16: hands return to normal; a bright closing tag.
  \oneVoice
  e'8 g16 a~ a8 g |
  f16 a f d~ d8 fis |
  g16 e c e g8 <b, d f> |
  <c e>8-> <e g c>-> r4\fermata \bar "|."
}

leftHand = \relative c {
  \common
  \clef bass
  % Alternating bass and offbeat chords.
  c8-. <e g>-. g,-. <e' g>-. |
  c8-. <e g>-. g,-. <e' g>-. |
  f,8-. <a c>-. c-. <a c>-. |
  c8-. <e g>-. g,-. <e' g>-. |
  c8-. <e g>-. e-. <g c>-. |
  a,8-. <c e>-. e-. <cis g'>-. |
  d8-. <f a>-. d-. <fis a>-. |
  g,8-. <b f'>-. g-. <b f'>-. |
  % The LEFT hand travels into the upper staff, above the R.H.
  \change Staff = "upper"
  \voiceOne
  \override TextSpanner.bound-details.left.text =
    \markup { \italic "L.H. over R.H. (bars 9–12)" }
  \override TextSpanner.bound-details.right.text =
    \markup { \draw-line #'(0 . -1) }
  \override TextSpanner.style = #'dashed-line
  \override TextSpanner.staff-padding = #3
  e''8\startTextSpan\mp g16 a~ a8 g |
  f16 a f c~ c8 f |
  a8 c16 a~ a8 fis |
  g16 b g d~ d8 b\stopTextSpan |
  \change Staff = "lower"
  \oneVoice
  c,,8-. <e g>-. g,-. <e' g>-. |
  d8-. <f a>-. d-. <fis a>-. |
  g,8-. <c e>-. g-. <b f'>-. |
  <c e g>8-> <c, c'>-> r4\fermata |
}

\score {
  \new PianoStaff <<
    \set PianoStaff.instrumentName = "Piano"
    \new Staff = "upper" { \rightHand }
    \new Staff = "lower" <<
      { \leftHand }
      { s2*8 R2*4 s2*4 }
    >>
  >>
  \layout {
    \context { \Score \override BarNumber.break-visibility = ##(#f #t #t) }
  }
  \midi { }
}
