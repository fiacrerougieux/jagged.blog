\version "2.24.0"

\header {
  title = "Espresso Rag"
  subtitle = "for café piano"
  tagline = ##f
}

% Right hand: bars 1-8 and 13-16 in treble; bars 9-12 move to the bass staff (below the LH)
rhMusic = {
  \clef treble \key c \major \time 2/4 \tempo "Tempo di Rag" 4 = 116
  e'8\mf g' c'' g' | f'8 e' d' c' | e'8 g' c'' g' | d''8 c'' b' g' |
  g'8 a' b' c'' | d''4 c''8 b' | a'8 g' f' e' | d'8 f' g'4 |
  \change Staff = "lower"
  c4 g | f4 c | d4 a, | g,4 c |
  \change Staff = "upper"
  c''8 e'' g'' e'' | d''8 c'' b' g' | e''8 d'' c'' a' | c''2 \bar "|."
}

% Left hand: bars 1-8 and 13-16 in bass; bars 9-12 cross up into the treble staff (above the RH)
lhMusic = {
  \clef bass \key c \major \time 2/4
  c4\p <g c'>4 | f,4 <c a>4 | c4 <g c'>4 | g,4 <d g>4 |
  c4 <g c'>4 | g,4 <d g>4 | f,4 <c f>4 | g,4 <d g>4 |
  \change Staff = "upper"
  e'8 g' c'' g' | a'8 g' f' e' | d'8 f' a'4 | g'8 e' c'4 |
  \change Staff = "lower"
  c4 <g c'>4 | g,4 <d g>4 | a,4 <e a>4 | c,2 \bar "|."
}

\score {
  \new PianoStaff <<
    \new Staff = "upper" <<
      \new Voice = "rh" { \rhMusic }
    >>
    \new Staff = "lower" <<
      \new Voice = "lh" { \lhMusic }
    >>
  >>
  \layout { }
}
