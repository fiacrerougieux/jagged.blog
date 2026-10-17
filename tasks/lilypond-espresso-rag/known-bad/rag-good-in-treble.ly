\version "2.24.1"
% Known good: for bars 9 to 12 the left hand is written into the treble staff as
% its own upper voice, labelled L.H., while the bass staff rests.
rh = {
  \clef treble \time 2/4
  \repeat unfold 8 { e''8 g'' c'' g'' | }
  <<
    { \voiceOne c'''8^\markup "L.H." e''' g''' e''' | \repeat unfold 3 { c'''8 e''' g''' e''' | } }
    \\
    { \voiceTwo r8 <e' g'>_\markup "R.H." r <e' g'> | \repeat unfold 3 { r8 <e' g'> r <e' g'> | } }
  >>
  \oneVoice
  e''8^\markup "Hands return" g'' c'' g'' | \repeat unfold 2 { e''8 g'' c'' g'' | } c''2 \bar "|."
}
lh = {
  \clef bass \time 2/4
  \repeat unfold 8 { c8 <e g> g, <e g> | }
  R2*4
  \repeat unfold 3 { c8 <e g> g, <e g> | } c2
}
\score { \new PianoStaff << \new Staff = "upper" \rh \new Staff = "lower" \lh >> \layout { } }
