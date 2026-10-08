\version "2.24.0"
\header {
  title = "Espresso Rag"
  subtitle = "A café piano rag — L.H. crosses over R.H. in bars 9–12"
  composer = ""
  tagline = ##f
}

rightHand = \relative c'' {
  \clef treble
  \key f \major
  \time 2/4
  \tempo "Bright, with a little swing" 4 = 116
  \voiceOne
  a8 c'8 f,8 a8 | g8 bes8 e,8 g8 |
  f8 a8 d,8 f8 | e8 g8 cis,8 e8 |
  d8 f8 bes,8 d8 | c8 e8 a,8 c8 |
  bes8 d8 g,8 bes8 | a8 c8 f,8 a8 |
  c'8 a8 f8 a8 | d8 bes8 g8 bes8 |
  c8 a8 f8 a8 | e8 c8 a8 c8 |
  f8 a8 c'8 a8 | e8 g8 bes8 g8 |
  d8 f8 a8 f8 | c8 e8 g8 c8 |
  \bar "|."
}

leftHand = \fixed c {
  \clef bass
  \key f \major
  \time 2/4
  \voiceTwo
  f,4 <c' f a>4 | c,4 <g' c e>4 |
  bes,4 <f' bes d>4 | f,4 <c' f a>4 |
  g,4 <d' g bes>4 | c,4 <g' c e>4 |
  f,4 <c' f a>4 | c,4 <g' c e>4 |
  R2 | R2 | R2 | R2 |
  f,4 <c' f a>4 | c,4 <g' c e>4 |
  bes,4 <f' bes d>4 | f,4 <c' f a>4 |
  \bar "|."
}

crossHand = \relative c'' {
  \key f \major
  \time 2/4
  \voiceTwo
  s2 | s2 | s2 | s2 | s2 | s2 | s2 | s2 |
  \transpose c c'' {
    <c f a>4 <a c f>4 | <d g bes>4 <bes d g>4 |
    <c f a>4 <a c f>4 | <e a c>4 <c e a>4 |
  }
  s2 | s2 | s2 | s2 |
}

\score {
  \new PianoStaff \with { instrumentName = "Piano" } <<
    \new Staff = "up" <<
      \new Voice = "right" { \rightHand }
      \new Voice = "cross" { \crossHand }
    >>
    \new Staff = "down" <<
      \new Voice = "left" { \leftHand }
    >>
  >>
  \layout {
    \context { \Score \override BarNumber.break-visibility = ##(#f #t #t) }
  }
}
