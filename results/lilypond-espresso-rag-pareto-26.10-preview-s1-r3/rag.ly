\version "2.24.1"

\header {
  title = "Espresso Rag"
  subtitle = "A little café two-step"
  tagline = ##f
}

\paper {
  #(set-paper-size "letter")
  indent = 0\mm
  system-system-spacing.basic-distance = #23
  system-system-spacing.minimum-distance = #18
}

global = { \key f \major \time 2/4 }

rightHand = {
  \global
  \clef treble
  \tempo "Brightly, with a light touch" 4 = 108
  % 1–4: syncopated opening, over a steady two-step bass.
  r16\mp c''16 e''16 f''16~ f''8 a''8-. |
  g''8-. e''16 c''16~ c''8 bes'8-. |
  a'16 d''16 fis''8~ fis''16 a''16 g''16 fis''16 |
  g''8-. d''8-. <e'' g''>4-> |
  \break
  % 5–8: answer and cadence.
  r16 c''16 e''16 f''16~ f''8 a''8-. |
  bes''8-. a''16 g''16~ g''8 f''8-. |
  e''16 g''16 bes''8~ bes''16 a''16 g''16 e''16 |
  <a' f''>8-. <g' e''>8-. <a' f''>4-> |
  \break
  % 9–12: upper voice played by the left hand throughout.
  <<
    {
      \voiceOne
      f'''8\mf^\markup { \bold "L.H. over R.H. (bars 9–12)" }
      d'''16 bes''16~ bes''8 d'''8-. |
      a''16 c'''16 f'''8~ f'''8 c'''8-. |
      d'''8-. bes''16 g''16~ g''8 bes''8-. |
      e'''16 d'''16 c'''8~ c'''16 bes''16 g''16 e''16 |
    }
    \\
    {
      \voiceTwo
      r8 <d' f'>8-._\markup { \italic "R.H." } r8 <d' f'>8-. |
      r8 <c' f'>8-. r8 <c' f'>8-. |
      r8 <d' g'>8-. r8 <d' g'>8-. |
      r8 <e' bes'>8-. r8 <e' bes'>8-. |
    }
  >>
  \oneVoice
  \break
  % 13–16: hands return; a crisp final cadence.
  r16\mp^\markup { \italic "Hands return" } c''16 e''16 f''16~ f''8 a''8-. |
  bes''8-. a''16 g''16~ g''8 fis''8-. |
  g''16 bes''16 d'''8-> c'''16 bes''16 g''16 e''16 |
  <a' c'' f''>8-> r8 <a' c'' f''>4-.\p \bar "|."
}

leftHand = {
  \global
  \clef bass
  % 1–8: F / C7 / D7 / Gm–C7, then the answering phrase.
  f,8-. <a c' f'>8-. c8-. <a c' f'>8-. |
  c8-. <g bes e'>8-. g,8-. <g bes e'>8-. |
  d8-. <a c' fis'>8-. a,8-. <a c' fis'>8-. |
  g,8-. <bes d' g'>8-. c8-. <bes e' g'>8-. |
  f,8-. <a c' f'>8-. c8-. <a c' f'>8-. |
  bes,8-. <bes d' f'>8-. b,8-. <a d' f'>8-. |
  c8-. <g bes e'>8-. g,8-. <g bes e'>8-. |
  f,8-. c8-. <f a c'>4-> |
  % The LH part is written in the treble staff during the crossover.
  R2*4 |
  f,8-. <a c' f'>8-. c8-. <a c' f'>8-. |
  bes,8-. <bes d' f'>8-. d8-. <a c' fis'>8-. |
  g,8-. <bes d' g'>8-. c8-. <bes e' g'>8-. |
  <f, c f>8-> r8 <f, c f>4-. \bar "|."
}

\score {
  \new PianoStaff <<
    \new Staff = "upper" { \rightHand }
    \new Staff = "lower" { \leftHand }
  >>
  \layout { }
  \midi { }
}
