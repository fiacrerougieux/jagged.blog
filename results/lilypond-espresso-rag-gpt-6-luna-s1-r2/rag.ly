\version "2.24.0"
\header {
  title = "Espresso Rag"
  subtitle = "A café piano rag"
  composer = ""
}

\score {
  \new PianoStaff \with { instrumentName = "Piano" } <<
    \new Staff = "upper" \with { \consists "Span_stem_engraver" } {
      \clef treble
      \key f \major
      \time 2/4
      \new Voice = "RH" {
        \voiceOne
        a'8 c'' f'' e'' | d'' c'' a' f' |
        g' bes' e'' d'' | c''4 a'8 f' |
        f'8 a' c'' d'' | ees'' d'' c'' a' |
        g' bes' d'' f'' | e''4 c''4 |
        \mark \markup \italic "L.H. over R.H. through bar 12"
        c'8 e' g' e' | d' f' a' f' |
        c'8 ees' g' ees' | d' f' a' c'' |
        f'8 a' c'' f'' | e'' d'' c'' a' |
        g' bes' d'' g'' | f''4 f'4 |
        \bar "|."
      }
    }
    \new Staff = "lower" {
      \clef bass
      \key f \major
      \time 2/4
      \new Voice = "LH" {
        \voiceOne
        f,4 <a, c>4 | c4 <g, c>4 |
        bes,4 <f a>4 | c4 <g, c>4 |
        f,4 <a, c>4 | c4 <g, c>4 |
        bes,4 <f a>4 | c4 <g, c>4 |
        \change Staff = "upper"
        \voiceTwo
        <f'' c'''>4 <f'' c'''>4 |
        <g'' d'''>4 <g'' d'''>4 |
        <ees'' c'''>4 <ees'' c'''>4 |
        <f'' c'''>4 <f'' c'''>4 |
        \change Staff = "lower"
        \voiceOne
        f,4 <a, c>4 | c4 <g, c>4 |
        bes,4 <f a>4 | f,4 <a, c>4 |
      }
    }
  >>
  \layout { }
  \midi { \tempo 4 = 132 }
}
