\version "2.24.1"

\header {
  title = "Espresso Rag"
  subtitle = "A café two-step"
  composer = ""
  tagline = ##f
}

\paper {
  #(set-paper-size "a4")
  indent = 12\mm
  short-indent = 0\mm
  top-margin = 12\mm
  bottom-margin = 12\mm
  system-system-spacing.basic-distance = #20
  ragged-last = ##f
}

global = {
  \key c \major
  \time 2/4
}

rightHand = {
  \global
  \tempo "Easy café rag (straight sixteenths)" 4 = 104
  \clef treble
  % 1–4: a crisp, syncopated café tune.
  e''8\mf-\markup { \italic "Light and jaunty" } g''16 a''~ a''8 g''8 |
  e''16 g'' e'' c''~ c''8 <e'' g''>8-. |
  f''8 a''16 c'''~ c'''8 a''8 |
  b''16 a'' g'' f''~ f''8 <b' d''>8-. | \break
  % 5–8: a little chromatic seasoning and a dominant turnaround.
  e''8 g''16 a''~ a''8 <e'' g''>8 |
  cis''16 e'' g'' a''~ a''8 g''8 |
  f''8 a''16 f''~ f''8 e''16 d'' |
  <b' d''>8-. <d'' f''>8-. <b' g''>4-> | \break
  % 9–12: the right hand accompanies BELOW the crossing left hand.
  \change Staff = "lower"
  \stemDown
  c'8\p^\markup { \italic "R.H. accompaniment" } <e' g'>8-. g8 <e' g'>8-. |
  c'8 <e' g'>8-. g8 <e' g'>8-. |
  c'8 <f' a'>8-. a8 <f' a'>8-. |
  b8 <f' g'>8-. g8 <f' g'>8-. | \break
  % 13–16: both hands return, then a compact closing flourish.
  \change Staff = "upper"
  \stemNeutral
  e''8\mf^\markup { \italic "Hands return" } g''16 a''~ a''8 g''8 |
  cis''16 e'' g'' a''~ a''8 <cis'' e''>8 |
  <d'' f''>8 a''16 f'' <b' d''>8 g''16 f'' |
  e''16 g'' c''' g'' <c'' e'' g''>4->\fermata \bar "|."
}

leftHand = {
  \global
  \clef bass
  % 1–8: dry, buoyant oom-pah; no sustained pedal.
  c8-\markup { \italic "Crisp bass; very little pedal" } <e g>8-. g,8 <e g>8-. |
  c8 <e g>8-. g,8 <e g>8-. |
  f,8 <a c'>8-. c8 <a c'>8-. |
  g,8 <b f'>8-. d8 <b f'>8-. |
  c8 <e g>8-. g,8 <e g>8-. |
  a,8 <cis g>8-. e8 <cis g>8-. |
  d8 <f a>8-. a,8 <f a>8-. |
  g,8 <b f'>8-. <g, g>4-> |
  % 9–12: actual cross-staff exchange; L.H. is above R.H.
  \clef treble
  \change Staff = "upper"
  \stemUp
  g''8\mp^\markup { \bold "L.H. over R.H. (bars 9–12)" } e''16 g''~ g''8 c'''8 |
  b''16 c''' b'' g''~ g''8 e''8 |
  a''8 c'''16 a''~ a''8 f''8 |
  g''16 a'' g'' f''~ f''8 d''8 |
  \change Staff = "lower"
  \clef bass
  \stemNeutral
  c8 <e g>8-. g,8 <e g>8-. |
  a,8 <cis g>8-. e8 <cis g>8-. |
  d8 <f a>8-. g,8 <b f'>8-. |
  c8 g,8 <c, c>4->\fermata
}

\score {
  \new PianoStaff \with { instrumentName = "Piano" } <<
    \new Staff = "upper" \with { midiInstrument = "acoustic grand" }
      { \rightHand }
    \new Staff = "lower" \with { midiInstrument = "acoustic grand" }
      { \leftHand }
  >>
  \layout {
    \context {
      \Score
      barNumberVisibility = #first-bar-number-invisible-save-broken-bars
      \override BarNumber.break-visibility = ##(#f #f #t)
    }
  }
  \midi { }
}
