\version "2.24.1"
% Known bad: both hands on the treble staff with stems left to LilyPond.
rh = {
  \clef treble \time 2/4
  \repeat unfold 8 { e''8 g'' c'' g'' | }
  
  \repeat unfold 4 { e'8 g' c' g' | }
  \oneVoice
  \repeat unfold 3 { e''8 g'' c'' g'' | } c''2 \bar "|."
}
lh = {
  \clef bass \time 2/4
  \repeat unfold 8 { c8 <e g> g, <e g> | }
  \change Staff = "upper" 
  c'''8^\markup "L.H." e''' g''' e''' | \repeat unfold 3 { c'''8 e''' g''' e''' | }
  \change Staff = "lower" \oneVoice
  c8^\markup "R.H. again" <e g> g, <e g> | \repeat unfold 2 { c8 <e g> g, <e g> | } c2
}
\score { \new PianoStaff << \new Staff = "upper" \rh \new Staff = "lower" \lh >> \layout { } }
