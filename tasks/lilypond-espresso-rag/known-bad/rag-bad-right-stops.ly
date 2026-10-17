\version "2.24.1"
% Known bad: the right hand rests for bars 9 to 12.
rh = {
  \clef treble \time 2/4
  \repeat unfold 8 { e''8 g'' c'' g'' | }
  \voiceTwo
  R2*4
  \oneVoice
  \repeat unfold 3 { e''8 g'' c'' g'' | } c''2 \bar "|."
}
lh = {
  \clef bass \time 2/4
  \repeat unfold 8 { c8 <e g> g, <e g> | }
  \change Staff = "upper" \voiceOne
  c'''8^\markup "L.H." e''' g''' e''' | \repeat unfold 3 { c'''8 e''' g''' e''' | }
  \change Staff = "lower" \oneVoice
  c8^\markup "R.H. again" <e g> g, <e g> | \repeat unfold 2 { c8 <e g> g, <e g> | } c2
}
\score { \new PianoStaff << \new Staff = "upper" \rh \new Staff = "lower" \lh >> \layout { } }
