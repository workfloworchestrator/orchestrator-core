# Search benchmark corpus

The `network_services` profile with random seed 2000: 3011 entities.

Update with `pytest test/unit_tests/benchmarks/search --inline-snapshot=fix`.

Every entity, anchors first, with the facts queries are made from: a query made from a fact expects every entity
that holds it. The indexed models hold much more, see `show_corpus` in the README.

| key                  | description                                    | identifier                                             | customer                     | location |
| -------------------- | ---------------------------------------------- | ------------------------------------------------------ | ---------------------------- | --- |
| ams001a-rt01         | NWR SP UNTAGGED AMS001A 10 Gbit/s              | ams001a-rt01                                           | Northwind Research, NWR      | Amsterdam |
| ams001a-rt10         | BFU SP UNTAGGED AMS001A 10 Gbit/s              | ams001a-rt10                                           | Bluefin University, BFU      | Amsterdam |
| asv001a-rt01         | RWI SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt01                                           | Redwood Institute, RWI       | Amstelveen |
| northwind-lightpath  | NWR LP AMS001A-RTD001A 10 Gbit/s               | ams001a-rt07, rtd001a-rt07                             | Northwind Research, NWR      | Amsterdam, Rotterdam |
| northwind-peering    | NWR IP UTR001A 10 Gbit/s                       | utr001a-rt02                                           | Northwind Research, NWR      | Utrecht |
| rtd001a-rt01         | SLM L2VPN EHV001A-RTD001A 10 Gbit/s            | rtd001a-rt01, ehv001a-rt03                             | Silverline Museum, SLM       | Rotterdam, Eindhoven |
| rmd001a-rt01         | SLA L2VPN ENS001A-RMD001A 10 Gbit/s            | rmd001a-rt01, ens001a-rt03                             | Silverline Archives, SLA     | Roermond, Enschede |
| rug-prefix-lir       | RUG prefix LIR 192.87.22.0/24                  | 192.87.22.0/24                                         | Rugby Institute, RUG         |  |
| rug-lr               | RUG LR ASD001B-GN012A ASD002A-GN001B 10 Gbit/s | asd001b-rt01, gn012a-rt01, asd002a-rt01, gn001b-rt01   | Rugby Institute, RUG         | Assen, Groningen |
| twin-ehv002a-mst001a | DLT LP EHV002A-MST001A 100 Gbit/s              | ehv002a-rt05, mst001a-rt05                             | Delta Institute, DLT         | Eindhoven, Maastricht |
| twin-ehv001a-mst002a | DLT LP EHV001A-MST002A 100 Gbit/s              | ehv001a-rt05, mst002a-rt05                             | Delta Institute, DLT         | Eindhoven, Maastricht |
| gen-1                | RWL IP GOR001A 100 Gbit/s                      | gor001a-rt12                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-2                | GFO LP GOR001A-GOR002A 100 Gbit/s              | gor002a-rt06, gor001a-rt01                             | Greenfield Observatory, GFO  | Gorinchem |
| gen-3                | BFH IP ASV001A 1 Gbit/s                        | asv001a-rt12                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4                | NWL IP ASV002A 1 Gbit/s                        | asv002a-rt04                                           | Northwind Labs, NWL          | Amstelveen |
| gen-5                | SLM IP AMS001A 1 Gbit/s                        | ams001a-rt02                                           | Silverline Museum, SLM       | Amsterdam |
| gen-7                | GFC LP AMS001A-ENS002A 1 Gbit/s                | ens002a-rt04, ams001a-rt08                             | Greenfield College, GFC      | Enschede, Amsterdam |
| gen-8                | RWL L2VPN ARN002A-GRQ001A 10 Gbit/s            | grq001a-rt10, arn002a-rt08                             | Redwood Libraries, RWL       | Groningen, Arnhem |
| gen-9                | RWL SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt01                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-10               | GFO L2VPN ARN001A-ASV001A-MST002A 10 Gbit/s    | mst002a-rt10, rmd001a-rt04, arn001a-rt05, asv001a-rt10 | Greenfield Observatory, GFO  | Maastricht, Roermond, Arnhem, Amstelveen |
| gen-12               | GFO L2VPN ARN002A-RTD001A 10 Gbit/s            | arn002a-rt05, rtd001a-rt06                             | Greenfield Observatory, GFO  | Arnhem, Rotterdam |
| gen-14               | BFU LP ARN001A-MST002A 10 Gbit/s               | arn001a-rt06, mst002a-rt09                             | Bluefin University, BFU      | Arnhem, Maastricht |
| gen-15               | NWR LP EHV001A-RMD002A 1 Gbit/s                | ehv001a-rt12, rmd002a-rt04                             | Northwind Research, NWR      | Eindhoven, Roermond |
| gen-16               | GFO IP GRQ002A 1 Gbit/s                        | grq002a-rt03                                           | Greenfield Observatory, GFO  | Groningen |
| gen-17               | SLA IP UTR002A 100 Gbit/s                      | utr002a-rt03                                           | Silverline Archives, SLA     | Utrecht |
| gen-19               | RWL SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt12                                           | Redwood Libraries, RWL       | Roermond |
| gen-20               | RWI SP TAGGED ALM002A 100 Gbit/s               | alm002a-rt02                                           | Redwood Institute, RWI       | Almere |
| gen-21               | RWL LP AMS002A-ARN002A 10 Gbit/s               | ams002a-rt10, arn002a-rt01                             | Redwood Libraries, RWL       | Amsterdam, Arnhem |
| gen-22               | GFO LP EHV002A-RTD002A 100 Gbit/s              | ehv002a-rt02, rtd002a-rt04                             | Greenfield Observatory, GFO  | Eindhoven, Rotterdam |
| gen-23               | GFO L2VPN ENS001A-GRQ001A-GRQ002A 1 Gbit/s     | utr001a-rt12, ens001a-rt01, grq002a-rt09, grq001a-rt01 | Greenfield Observatory, GFO  | Utrecht, Enschede, Groningen |
| gen-26               | BFU L2VPN ENS001A-GRQ001A 10 Gbit/s            | ens001a-rt11, grq001a-rt02                             | Bluefin University, BFU      | Enschede, Groningen |
| gen-27               | SLA SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt12                                           | Silverline Archives, SLA     | Amsterdam |
| gen-31               | BFH L2VPN EHV002A-GRQ001A 1 Gbit/s             | ehv002a-rt12, grq001a-rt07, grq001a-rt06               | Bluefin Hospital, BFH        | Eindhoven, Groningen |
| gen-32               | BFH L2VPN ALM002A-RMD001A 100 Gbit/s           | rmd001a-rt05, alm002a-rt01                             | Bluefin Hospital, BFH        | Roermond, Almere |
| gen-34               | RWI SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt08                                           | Redwood Institute, RWI       | Arnhem |
| gen-37               | RWL IP RMD001A 10 Gbit/s                       | rmd001a-rt03                                           | Redwood Libraries, RWL       | Roermond |
| gen-38               | RWI L2VPN EHV001A-RTD001A 1 Gbit/s             | ehv001a-rt06, rtd001a-rt09                             | Redwood Institute, RWI       | Eindhoven, Rotterdam |
| gen-39               | RWL SP TAGGED EHV002A 10 Gbit/s                | ehv002a-rt04                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-40               | RWI L2VPN GOR002A-RTD001A 100 Gbit/s           | rtd001a-rt12, gor002a-rt03                             | Redwood Institute, RWI       | Rotterdam, Gorinchem |
| gen-41               | BFU SP TAGGED RMD001A 1 Gbit/s                 | rmd001a-rt12                                           | Bluefin University, BFU      | Roermond |
| gen-43               | GFC IP GOR002A 10 Gbit/s                       | gor002a-rt03                                           | Greenfield College, GFC      | Gorinchem |
| gen-45               | NWL IP ARN001A 10 Gbit/s                       | arn001a-rt01                                           | Northwind Labs, NWL          | Arnhem |
| gen-47               | GFO IP GOR002A 100 Gbit/s                      | gor002a-rt01                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-49               | GFO L2VPN GRQ001A-GRQ002A-MST001A 100 Gbit/s   | grq002a-rt04, grq001a-rt09, mst001a-rt04               | Greenfield Observatory, GFO  | Groningen, Maastricht |
| gen-50               | BFH SP TAGGED UTR001A 10 Gbit/s                | utr001a-rt08                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-54               | NWR SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt02                                           | Northwind Research, NWR      | Arnhem |
| gen-56               | RWL SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt12                                           | Redwood Libraries, RWL       | Enschede |
| gen-57               | RWI SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt05                                           | Redwood Institute, RWI       | Arnhem |
| gen-58               | GFC SP TAGGED RMD001A 1 Gbit/s                 | rmd001a-rt06                                           | Greenfield College, GFC      | Roermond |
| gen-59               | NWL L2VPN ENS001A-MST002A 100 Gbit/s           | ens001a-rt06, mst002a-rt06                             | Northwind Labs, NWL          | Enschede, Maastricht |
| gen-62               | NWL SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt12                                           | Northwind Labs, NWL          | Arnhem |
| gen-63               | NWR LP EHV001A-ENS002A 100 Gbit/s              | ehv001a-rt11, ens002a-rt04                             | Northwind Research, NWR      | Eindhoven, Enschede |
| gen-65               | BFU SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt11                                           | Bluefin University, BFU      | Eindhoven |
| gen-66               | NWL L2VPN GRQ001A-MST001A 1 Gbit/s             | grq001a-rt12, mst001a-rt08                             | Northwind Labs, NWL          | Groningen, Maastricht |
| gen-68               | BFH IP ASV001A 1 Gbit/s                        | asv001a-rt05                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-70               | BFH L2VPN ALM001A-ARN001A-ENS002A 100 Gbit/s   | arn001a-rt11, mst002a-rt08, ens002a-rt05, alm001a-rt12 | Bluefin Hospital, BFH        | Arnhem, Maastricht, Enschede, Almere |
| gen-73               | RWL IP RMD002A 1 Gbit/s                        | rmd002a-rt07                                           | Redwood Libraries, RWL       | Roermond |
| gen-74               | BFH SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt04                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-76               | SLA L2VPN ASV001A-GRQ002A-MST001A 100 Gbit/s   | asv001a-rt03, utr002a-rt11, grq002a-rt05, mst001a-rt07 | Silverline Archives, SLA     | Amstelveen, Utrecht, Groningen, Maastricht |
| gen-77               | SLM IP GRQ002A 1 Gbit/s                        | grq002a-rt08                                           | Silverline Museum, SLM       | Groningen |
| gen-78               | NWR SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt06                                           | Northwind Research, NWR      | Enschede |
| gen-79               | SLM L2VPN ALM001A-GRQ001A-MST002A 10 Gbit/s    | grq001a-rt01, mst002a-rt10, alm001a-rt03, utr001a-rt08 | Silverline Museum, SLM       | Groningen, Maastricht, Almere, Utrecht |
| gen-80               | GFO IP GRQ001A 100 Gbit/s                      | grq001a-rt07                                           | Greenfield Observatory, GFO  | Groningen |
| gen-81               | BFU L2VPN ALM001A-ARN001A-ASV001A 10 Gbit/s    | arn001a-rt10, utr002a-rt01, asv001a-rt03, alm001a-rt01 | Bluefin University, BFU      | Arnhem, Utrecht, Amstelveen, Almere |
| gen-82               | SLM IP AMS001A 10 Gbit/s                       | ams001a-rt05                                           | Silverline Museum, SLM       | Amsterdam |
| gen-83               | RWL L2VPN ALM002A-GOR001A-GRQ001A 100 Gbit/s   | alm002a-rt06, alm002a-rt07, gor001a-rt02, grq001a-rt09 | Redwood Libraries, RWL       | Almere, Gorinchem, Groningen |
| gen-84               | BFU LP MST001A-RMD002A 100 Gbit/s              | mst001a-rt07, rmd002a-rt03                             | Bluefin University, BFU      | Maastricht, Roermond |
| gen-85               | GFC IP ALM001A 100 Gbit/s                      | alm001a-rt03                                           | Greenfield College, GFC      | Almere |
| gen-86               | RWL SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-87               | NWR L2VPN ALM001A-ARN002A-RMD002A 100 Gbit/s   | rmd002a-rt02, alm001a-rt09, arn002a-rt05               | Northwind Research, NWR      | Roermond, Almere, Arnhem |
| gen-88               | GFO LP GRQ002A-UTR001A 1 Gbit/s                | utr001a-rt12, grq002a-rt05                             | Greenfield Observatory, GFO  | Utrecht, Groningen |
| gen-89               | GFC IP RMD002A 1 Gbit/s                        | rmd002a-rt09                                           | Greenfield College, GFC      | Roermond |
| gen-91               | GFC IP ARN001A 100 Gbit/s                      | arn001a-rt09                                           | Greenfield College, GFC      | Arnhem |
| gen-93               | GFO SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt11                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-94               | GFC LP ENS002A-RTD002A 100 Gbit/s              | ens002a-rt10, rtd002a-rt02                             | Greenfield College, GFC      | Enschede, Rotterdam |
| gen-95               | NWL SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt11                                           | Northwind Labs, NWL          | Groningen |
| gen-96               | GFO LP ALM001A-UTR002A 100 Gbit/s              | utr002a-rt09, alm001a-rt01                             | Greenfield Observatory, GFO  | Utrecht, Almere |
| gen-97               | RWI L2VPN ARN002A-EHV001A-GOR002A 1 Gbit/s     | arn002a-rt05, ehv001a-rt07, gor002a-rt01               | Redwood Institute, RWI       | Arnhem, Eindhoven, Gorinchem |
| gen-98               | RWL IP AMS001A 1 Gbit/s                        | ams001a-rt08                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-99               | GFO LP ALM001A-RTD002A 1 Gbit/s                | alm001a-rt12, rtd002a-rt11                             | Greenfield Observatory, GFO  | Almere, Rotterdam |
| gen-101              | SLA SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt12                                           | Silverline Archives, SLA     | Almere |
| gen-102              | GFO LP ALM001A-EHV002A 100 Gbit/s              | ehv002a-rt04, alm001a-rt08                             | Greenfield Observatory, GFO  | Eindhoven, Almere |
| gen-105              | SLA SP UNTAGGED AMS001A 100 Gbit/s             | ams001a-rt06                                           | Silverline Archives, SLA     | Amsterdam |
| gen-106              | BFU IP ENS002A 10 Gbit/s                       | ens002a-rt12                                           | Bluefin University, BFU      | Enschede |
| gen-109              | RWL IP RMD001A 1 Gbit/s                        | rmd001a-rt02                                           | Redwood Libraries, RWL       | Roermond |
| gen-110              | GFO SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt05                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-112              | RWI L2VPN EHV001A-GRQ001A-GRQ002A 1 Gbit/s     | grq001a-rt11, grq002a-rt06, ehv001a-rt08               | Redwood Institute, RWI       | Groningen, Eindhoven |
| gen-113              | GFO IP UTR002A 100 Gbit/s                      | utr002a-rt08                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-115              | NWR IP ARN001A 1 Gbit/s                        | arn001a-rt09                                           | Northwind Research, NWR      | Arnhem |
| gen-116              | GFC SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt08                                           | Greenfield College, GFC      | Arnhem |
| gen-117              | RWI LP ENS002A-GRQ002A 100 Gbit/s              | grq002a-rt10, ens002a-rt05                             | Redwood Institute, RWI       | Groningen, Enschede |
| gen-119              | NWR IP GOR002A 10 Gbit/s                       | gor002a-rt12                                           | Northwind Research, NWR      | Gorinchem |
| gen-120              | GFO SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt11                                           | Greenfield Observatory, GFO  | Enschede |
| gen-121              | GFC L2VPN AMS002A-GOR001A-UTR002A 100 Gbit/s   | ams002a-rt09, utr002a-rt12, gor001a-rt12               | Greenfield College, GFC      | Amsterdam, Utrecht, Gorinchem |
| gen-124              | RWI IP GOR002A 100 Gbit/s                      | gor002a-rt06                                           | Redwood Institute, RWI       | Gorinchem |
| gen-125              | BFH IP RTD002A 1 Gbit/s                        | rtd002a-rt11                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-126              | BFU LP ALM001A-GOR001A 10 Gbit/s               | alm001a-rt12, gor001a-rt01                             | Bluefin University, BFU      | Almere, Gorinchem |
| gen-127              | BFH IP RTD002A 100 Gbit/s                      | rtd002a-rt11                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-128              | RWI LP RMD001A-UTR002A 10 Gbit/s               | utr002a-rt04, rmd001a-rt07                             | Redwood Institute, RWI       | Utrecht, Roermond |
| gen-130              | SLA IP ASV001A 1 Gbit/s                        | asv001a-rt10                                           | Silverline Archives, SLA     | Amstelveen |
| gen-133              | BFH L2VPN ASV002A-ENS001A 10 Gbit/s            | ens001a-rt02, asv002a-rt09                             | Bluefin Hospital, BFH        | Enschede, Amstelveen |
| gen-135              | NWL L2VPN EHV002A-GRQ001A 100 Gbit/s           | ehv002a-rt06, grq001a-rt10                             | Northwind Labs, NWL          | Eindhoven, Groningen |
| gen-136              | SLM LP AMS002A-GRQ002A 1 Gbit/s                | ams002a-rt10, grq002a-rt12                             | Silverline Museum, SLM       | Amsterdam, Groningen |
| gen-137              | GFC SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt08                                           | Greenfield College, GFC      | Almere |
| gen-138              | RWI IP MST001A 1 Gbit/s                        | mst001a-rt01                                           | Redwood Institute, RWI       | Maastricht |
| gen-139              | RWL IP ENS002A 1 Gbit/s                        | ens002a-rt08                                           | Redwood Libraries, RWL       | Enschede |
| gen-140              | NWL L2VPN ALM002A-GOR001A-MST002A 100 Gbit/s   | mst002a-rt03, alm002a-rt10, gor001a-rt11               | Northwind Labs, NWL          | Maastricht, Almere, Gorinchem |
| gen-143              | BFU IP ASV001A 10 Gbit/s                       | asv001a-rt11                                           | Bluefin University, BFU      | Amstelveen |
| gen-145              | GFC SP UNTAGGED RMD002A 1 Gbit/s               | rmd002a-rt11                                           | Greenfield College, GFC      | Roermond |
| gen-146              | BFU L2VPN ARN002A-ENS002A-UTR002A 100 Gbit/s   | utr002a-rt02, ens002a-rt05, arn002a-rt08               | Bluefin University, BFU      | Utrecht, Enschede, Arnhem |
| gen-147              | BFU LP RMD001A-RMD002A 1 Gbit/s                | rmd002a-rt08, rmd001a-rt07                             | Bluefin University, BFU      | Roermond |
| gen-148              | BFU LP ASV002A-UTR001A 10 Gbit/s               | asv002a-rt02, utr001a-rt12                             | Bluefin University, BFU      | Amstelveen, Utrecht |
| gen-150              | GFO L2VPN ENS001A-GOR002A-GRQ002A 10 Gbit/s    | ens001a-rt06, gor002a-rt08, grq002a-rt10, rtd001a-rt06 | Greenfield Observatory, GFO  | Enschede, Gorinchem, Groningen, Rotterdam |
| gen-151              | BFU L2VPN ARN001A-RMD002A-UTR001A 100 Gbit/s   | utr001a-rt12, rmd002a-rt08, arn001a-rt04               | Bluefin University, BFU      | Utrecht, Roermond, Arnhem |
| gen-152              | GFO SP UNTAGGED RTD002A 10 Gbit/s              | rtd002a-rt03                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-154              | NWL IP ALM001A 1 Gbit/s                        | alm001a-rt12                                           | Northwind Labs, NWL          | Almere |
| gen-155              | GFO LP MST001A-RMD002A 10 Gbit/s               | rmd002a-rt10, mst001a-rt04                             | Greenfield Observatory, GFO  | Roermond, Maastricht |
| gen-156              | BFU SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt03                                           | Bluefin University, BFU      | Groningen |
| gen-157              | GFC LP EHV001A-RTD001A 1 Gbit/s                | ehv001a-rt01, rtd001a-rt04                             | Greenfield College, GFC      | Eindhoven, Rotterdam |
| gen-158              | NWL LP ARN002A-EHV002A 100 Gbit/s              | arn002a-rt09, ehv002a-rt07                             | Northwind Labs, NWL          | Arnhem, Eindhoven |
| gen-159              | NWR L2VPN ASV002A-GOR001A-GOR002A 10 Gbit/s    | gor001a-rt08, gor002a-rt09, asv002a-rt08               | Northwind Research, NWR      | Gorinchem, Amstelveen |
| gen-160              | SLA IP GRQ002A 100 Gbit/s                      | grq002a-rt02                                           | Silverline Archives, SLA     | Groningen |
| gen-161              | GFO LP ALM001A-ALM002A 100 Gbit/s              | alm001a-rt04, alm002a-rt01                             | Greenfield Observatory, GFO  | Almere |
| gen-162              | NWR IP EHV001A 10 Gbit/s                       | ehv001a-rt08                                           | Northwind Research, NWR      | Eindhoven |
| gen-164              | RWI SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt10                                           | Redwood Institute, RWI       | Utrecht |
| gen-165              | NWR IP RMD002A 10 Gbit/s                       | rmd002a-rt01                                           | Northwind Research, NWR      | Roermond |
| gen-166              | BFU SP UNTAGGED RTD001A 10 Gbit/s              | rtd001a-rt05                                           | Bluefin University, BFU      | Rotterdam |
| gen-167              | BFH SP TAGGED GOR001A 100 Gbit/s               | gor001a-rt09                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-168              | NWL LP ALM002A-ASV002A 100 Gbit/s              | alm002a-rt07, asv002a-rt06                             | Northwind Labs, NWL          | Almere, Amstelveen |
| gen-170              | NWR LP ALM001A-MST001A 10 Gbit/s               | alm001a-rt03, mst001a-rt02                             | Northwind Research, NWR      | Almere, Maastricht |
| gen-171              | GFO IP MST002A 10 Gbit/s                       | mst002a-rt02                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-174              | SLM SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt06                                           | Silverline Museum, SLM       | Amsterdam |
| gen-176              | BFU IP MST001A 10 Gbit/s                       | mst001a-rt02                                           | Bluefin University, BFU      | Maastricht |
| gen-177              | RWL L2VPN ALM001A-ALM002A-GOR001A 1 Gbit/s     | rmd002a-rt06, alm002a-rt07, gor001a-rt12, alm001a-rt06 | Redwood Libraries, RWL       | Roermond, Almere, Gorinchem |
| gen-178              | BFU IP EHV001A 10 Gbit/s                       | ehv001a-rt09                                           | Bluefin University, BFU      | Eindhoven |
| gen-179              | SLM IP ASV001A 10 Gbit/s                       | asv001a-rt08                                           | Silverline Museum, SLM       | Amstelveen |
| gen-180              | RWI LP ARN001A-MST002A 100 Gbit/s              | arn001a-rt11, mst002a-rt12                             | Redwood Institute, RWI       | Arnhem, Maastricht |
| gen-182              | RWI L2VPN AMS001A-UTR002A 1 Gbit/s             | ams001a-rt04, utr002a-rt11                             | Redwood Institute, RWI       | Amsterdam, Utrecht |
| gen-183              | SLM IP ARN001A 100 Gbit/s                      | arn001a-rt04                                           | Silverline Museum, SLM       | Arnhem |
| gen-184              | SLA L2VPN ALM001A-GRQ002A 10 Gbit/s            | alm001a-rt06, grq002a-rt02                             | Silverline Archives, SLA     | Almere, Groningen |
| gen-186              | BFU SP UNTAGGED GOR002A 1 Gbit/s               | gor002a-rt08                                           | Bluefin University, BFU      | Gorinchem |
| gen-187              | BFU LP ARN001A-ASV001A 100 Gbit/s              | asv001a-rt11, arn001a-rt10                             | Bluefin University, BFU      | Amstelveen, Arnhem |
| gen-188              | RWI LP AMS002A-ARN002A 1 Gbit/s                | arn002a-rt03, ams002a-rt07                             | Redwood Institute, RWI       | Arnhem, Amsterdam |
| gen-192              | NWR SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt12                                           | Northwind Research, NWR      | Maastricht |
| gen-194              | GFO L2VPN AMS002A-MST002A-RMD001A 1 Gbit/s     | rmd001a-rt11, utr002a-rt09, mst002a-rt08, ams002a-rt09 | Greenfield Observatory, GFO  | Roermond, Utrecht, Maastricht, Amsterdam |
| gen-195              | GFC L2VPN ENS002A-GOR002A-GRQ001A 1 Gbit/s     | ens002a-rt04, mst002a-rt07, gor002a-rt05, grq001a-rt09 | Greenfield College, GFC      | Enschede, Maastricht, Gorinchem, Groningen |
| gen-197              | SLA LP GRQ001A-UTR002A 10 Gbit/s               | utr002a-rt08, grq001a-rt12                             | Silverline Archives, SLA     | Utrecht, Groningen |
| gen-200              | BFU SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt12                                           | Bluefin University, BFU      | Almere |
| gen-201              | RWI L2VPN ARN002A-EHV002A-MST001A 10 Gbit/s    | ehv002a-rt08, mst001a-rt01, arn002a-rt11, rmd001a-rt05 | Redwood Institute, RWI       | Eindhoven, Maastricht, Arnhem, Roermond |
| gen-202              | GFO LP GRQ001A-RTD001A 10 Gbit/s               | grq001a-rt10, rtd001a-rt12                             | Greenfield Observatory, GFO  | Groningen, Rotterdam |
| gen-205              | NWL SP UNTAGGED MST002A 100 Gbit/s             | mst002a-rt01                                           | Northwind Labs, NWL          | Maastricht |
| gen-208              | GFO IP AMS002A 1 Gbit/s                        | ams002a-rt07                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-209              | RWL IP RMD001A 100 Gbit/s                      | rmd001a-rt12                                           | Redwood Libraries, RWL       | Roermond |
| gen-210              | BFU LP GOR002A-UTR001A 100 Gbit/s              | utr001a-rt06, gor002a-rt04                             | Bluefin University, BFU      | Utrecht, Gorinchem |
| gen-211              | GFO LP AMS002A-MST001A 100 Gbit/s              | mst001a-rt10, ams002a-rt06                             | Greenfield Observatory, GFO  | Maastricht, Amsterdam |
| gen-212              | NWL LP EHV002A-RMD002A 1 Gbit/s                | ehv002a-rt11, rmd002a-rt06                             | Northwind Labs, NWL          | Eindhoven, Roermond |
| gen-214              | SLA SP UNTAGGED ASV002A 1 Gbit/s               | asv002a-rt04                                           | Silverline Archives, SLA     | Amstelveen |
| gen-215              | SLM LP ARN002A-GRQ002A 1 Gbit/s                | grq002a-rt09, arn002a-rt05                             | Silverline Museum, SLM       | Groningen, Arnhem |
| gen-216              | SLM IP UTR002A 100 Gbit/s                      | utr002a-rt05                                           | Silverline Museum, SLM       | Utrecht |
| gen-217              | RWI SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt02                                           | Redwood Institute, RWI       | Almere |
| gen-218              | GFO LP AMS001A-ARN002A 1 Gbit/s                | ams001a-rt03, arn002a-rt02                             | Greenfield Observatory, GFO  | Amsterdam, Arnhem |
| gen-219              | BFU SP UNTAGGED ARN002A 100 Gbit/s             | arn002a-rt04                                           | Bluefin University, BFU      | Arnhem |
| gen-220              | BFH SP TAGGED ASV001A 1 Gbit/s                 | asv001a-rt11                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-221              | RWI L2VPN ALM001A-AMS001A-GOR001A 1 Gbit/s     | ams001a-rt08, gor001a-rt03, rmd001a-rt05, alm001a-rt02 | Redwood Institute, RWI       | Amsterdam, Gorinchem, Roermond, Almere |
| gen-222              | GFO L2VPN ARN001A-ENS001A-MST001A 1 Gbit/s     | arn001a-rt02, rtd001a-rt09, ens001a-rt01, mst001a-rt01 | Greenfield Observatory, GFO  | Arnhem, Rotterdam, Enschede, Maastricht |
| gen-225              | GFC IP GOR002A 1 Gbit/s                        | gor002a-rt05                                           | Greenfield College, GFC      | Gorinchem |
| gen-226              | BFU SP UNTAGGED ALM002A 100 Gbit/s             | alm002a-rt12                                           | Bluefin University, BFU      | Almere |
| gen-227              | NWL IP GOR002A 100 Gbit/s                      | gor002a-rt02                                           | Northwind Labs, NWL          | Gorinchem |
| gen-228              | GFO IP EHV001A 10 Gbit/s                       | ehv001a-rt08                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-230              | BFH SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt11                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-231              | NWR IP MST001A 100 Gbit/s                      | mst001a-rt07                                           | Northwind Research, NWR      | Maastricht |
| gen-232              | GFO LP ARN002A-ASV002A 100 Gbit/s              | arn002a-rt01, asv002a-rt09                             | Greenfield Observatory, GFO  | Arnhem, Amstelveen |
| gen-233              | BFU SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt04                                           | Bluefin University, BFU      | Amstelveen |
| gen-234              | BFH L2VPN ARN002A-RTD002A 1 Gbit/s             | arn002a-rt08, rtd002a-rt04                             | Bluefin Hospital, BFH        | Arnhem, Rotterdam |
| gen-236              | SLA IP ASV001A 10 Gbit/s                       | asv001a-rt10                                           | Silverline Archives, SLA     | Amstelveen |
| gen-237              | BFH LP EHV001A-GOR001A 100 Gbit/s              | ehv001a-rt06, gor001a-rt10                             | Bluefin Hospital, BFH        | Eindhoven, Gorinchem |
| gen-239              | SLA LP ASV002A-GRQ002A 10 Gbit/s               | grq002a-rt07, asv002a-rt09                             | Silverline Archives, SLA     | Groningen, Amstelveen |
| gen-240              | RWL IP GOR002A 1 Gbit/s                        | gor002a-rt04                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-243              | NWR SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt09                                           | Northwind Research, NWR      | Maastricht |
| gen-244              | SLM L2VPN GOR001A-MST001A-UTR001A 100 Gbit/s   | gor001a-rt06, mst001a-rt09, utr001a-rt10               | Silverline Museum, SLM       | Gorinchem, Maastricht, Utrecht |
| gen-247              | RWI L2VPN ARN002A-ENS001A-MST002A 100 Gbit/s   | ens001a-rt11, rtd002a-rt12, mst002a-rt04, arn002a-rt07 | Redwood Institute, RWI       | Enschede, Rotterdam, Maastricht, Arnhem |
| gen-248              | BFH L2VPN ALM002A-EHV001A-MST002A 100 Gbit/s   | ehv001a-rt07, mst002a-rt06, mst002a-rt12, alm002a-rt05 | Bluefin Hospital, BFH        | Eindhoven, Maastricht, Almere |
| gen-249              | RWI LP GRQ001A-MST001A 10 Gbit/s               | grq001a-rt07, mst001a-rt01                             | Redwood Institute, RWI       | Groningen, Maastricht |
| gen-250              | GFC SP TAGGED RMD002A 100 Gbit/s               | rmd002a-rt12                                           | Greenfield College, GFC      | Roermond |
| gen-252              | NWL L2VPN ASV002A-RMD001A 10 Gbit/s            | asv002a-rt09, rmd001a-rt06                             | Northwind Labs, NWL          | Amstelveen, Roermond |
| gen-253              | GFC L2VPN ARN002A-ASV002A-EHV001A 10 Gbit/s    | asv002a-rt02, ehv001a-rt08, arn002a-rt04               | Greenfield College, GFC      | Amstelveen, Eindhoven, Arnhem |
| gen-254              | BFU IP EHV001A 1 Gbit/s                        | ehv001a-rt06                                           | Bluefin University, BFU      | Eindhoven |
| gen-255              | GFC IP ARN001A 100 Gbit/s                      | arn001a-rt01                                           | Greenfield College, GFC      | Arnhem |
| gen-256              | SLM SP UNTAGGED AMS001A 10 Gbit/s              | ams001a-rt08                                           | Silverline Museum, SLM       | Amsterdam |
| gen-257              | GFC SP UNTAGGED AMS002A 10 Gbit/s              | ams002a-rt05                                           | Greenfield College, GFC      | Amsterdam |
| gen-259              | GFO L2VPN AMS002A-EHV002A-RMD002A 1 Gbit/s     | ehv002a-rt04, ams002a-rt11, rmd002a-rt08               | Greenfield Observatory, GFO  | Eindhoven, Amsterdam, Roermond |
| gen-260              | NWL IP GOR002A 100 Gbit/s                      | gor002a-rt06                                           | Northwind Labs, NWL          | Gorinchem |
| gen-261              | RWL LP MST001A-RTD002A 10 Gbit/s               | rtd002a-rt04, mst001a-rt07                             | Redwood Libraries, RWL       | Rotterdam, Maastricht |
| gen-262              | BFH SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt07                                           | Bluefin Hospital, BFH        | Almere |
| gen-263              | GFO IP EHV002A 1 Gbit/s                        | ehv002a-rt06                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-264              | NWR L2VPN GOR001A-MST001A 10 Gbit/s            | mst001a-rt10, gor001a-rt11, mst001a-rt08               | Northwind Research, NWR      | Maastricht, Gorinchem |
| gen-265              | BFU L2VPN ASV002A-ENS002A-GRQ001A 1 Gbit/s     | grq001a-rt11, ens002a-rt05, asv002a-rt05               | Bluefin University, BFU      | Groningen, Enschede, Amstelveen |
| gen-267              | GFO L2VPN ASV001A-ASV002A-ENS002A 1 Gbit/s     | asv001a-rt09, ens002a-rt01, asv002a-rt09               | Greenfield Observatory, GFO  | Amstelveen, Enschede |
| gen-268              | RWI LP MST001A-RMD002A 10 Gbit/s               | mst001a-rt12, rmd002a-rt01                             | Redwood Institute, RWI       | Maastricht, Roermond |
| gen-269              | SLM IP MST001A 10 Gbit/s                       | mst001a-rt10                                           | Silverline Museum, SLM       | Maastricht |
| gen-270              | SLA SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt08                                           | Silverline Archives, SLA     | Arnhem |
| gen-271              | RWI L2VPN ALM002A-ENS002A 10 Gbit/s            | alm002a-rt10, ens002a-rt11                             | Redwood Institute, RWI       | Almere, Enschede |
| gen-272              | BFU LP ARN001A-GRQ002A 100 Gbit/s              | arn001a-rt02, grq002a-rt05                             | Bluefin University, BFU      | Arnhem, Groningen |
| gen-274              | GFO L2VPN AMS001A-EHV002A-UTR002A 1 Gbit/s     | ams001a-rt09, utr002a-rt06, ehv002a-rt09               | Greenfield Observatory, GFO  | Amsterdam, Utrecht, Eindhoven |
| gen-275              | GFO SP UNTAGGED GRQ001A 1 Gbit/s               | grq001a-rt06                                           | Greenfield Observatory, GFO  | Groningen |
| gen-277              | GFO SP UNTAGGED ENS002A 10 Gbit/s              | ens002a-rt01                                           | Greenfield Observatory, GFO  | Enschede |
| gen-279              | GFO LP MST001A-RTD001A 100 Gbit/s              | mst001a-rt07, rtd001a-rt03                             | Greenfield Observatory, GFO  | Maastricht, Rotterdam |
| gen-280              | SLA IP ALM001A 10 Gbit/s                       | alm001a-rt02                                           | Silverline Archives, SLA     | Almere |
| gen-281              | SLM L2VPN ALM001A-GRQ001A-UTR001A 100 Gbit/s   | alm001a-rt04, grq001a-rt05, utr001a-rt09               | Silverline Museum, SLM       | Almere, Groningen, Utrecht |
| gen-282              | SLA L2VPN ARN002A-GOR001A-MST002A 100 Gbit/s   | utr001a-rt09, gor001a-rt12, arn002a-rt01, mst002a-rt07 | Silverline Archives, SLA     | Utrecht, Gorinchem, Arnhem, Maastricht |
| gen-283              | BFH IP ARN001A 100 Gbit/s                      | arn001a-rt09                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-284              | RWI LP EHV001A-RMD001A 10 Gbit/s               | rmd001a-rt06, ehv001a-rt04                             | Redwood Institute, RWI       | Roermond, Eindhoven |
| gen-285              | GFC L2VPN AMS001A-GOR002A-RMD001A 10 Gbit/s    | rmd001a-rt11, gor002a-rt05, ams001a-rt04               | Greenfield College, GFC      | Roermond, Gorinchem, Amsterdam |
| gen-287              | GFO L2VPN ALM002A-GOR001A 100 Gbit/s           | alm002a-rt08, gor001a-rt09                             | Greenfield Observatory, GFO  | Almere, Gorinchem |
| gen-288              | NWL SP TAGGED GRQ002A 10 Gbit/s                | grq002a-rt05                                           | Northwind Labs, NWL          | Groningen |
| gen-289              | NWL IP ARN002A 100 Gbit/s                      | arn002a-rt03                                           | Northwind Labs, NWL          | Arnhem |
| gen-290              | RWI IP MST002A 100 Gbit/s                      | mst002a-rt12                                           | Redwood Institute, RWI       | Maastricht |
| gen-293              | RWI SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt09                                           | Redwood Institute, RWI       | Roermond |
| gen-294              | GFC IP RTD002A 100 Gbit/s                      | rtd002a-rt12                                           | Greenfield College, GFC      | Rotterdam |
| gen-295              | RWI L2VPN GRQ001A-GRQ002A-MST002A 100 Gbit/s   | grq002a-rt11, mst002a-rt08, grq001a-rt09               | Redwood Institute, RWI       | Groningen, Maastricht |
| gen-297              | BFH SP TAGGED UTR002A 100 Gbit/s               | utr002a-rt10                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-298              | NWL SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt05                                           | Northwind Labs, NWL          | Enschede |
| gen-299              | RWI IP ARN001A 10 Gbit/s                       | arn001a-rt03                                           | Redwood Institute, RWI       | Arnhem |
| gen-300              | GFO L2VPN RMD001A-RMD002A 100 Gbit/s           | rmd001a-rt12, rmd002a-rt07                             | Greenfield Observatory, GFO  | Roermond |
| gen-302              | GFO IP RMD002A 10 Gbit/s                       | rmd002a-rt03                                           | Greenfield Observatory, GFO  | Roermond |
| gen-303              | RWL SP UNTAGGED RMD002A 1 Gbit/s               | rmd002a-rt04                                           | Redwood Libraries, RWL       | Roermond |
| gen-304              | NWL L2VPN ALM001A-ASV002A-GRQ001A 100 Gbit/s   | alm001a-rt06, asv002a-rt06, grq001a-rt01               | Northwind Labs, NWL          | Almere, Amstelveen, Groningen |
| gen-305              | BFH SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt02                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-306              | RWI SP TAGGED AMS002A 10 Gbit/s                | ams002a-rt04                                           | Redwood Institute, RWI       | Amsterdam |
| gen-307              | BFH L2VPN ASV002A-EHV001A-GOR001A 10 Gbit/s    | asv002a-rt09, rtd002a-rt03, gor001a-rt01, ehv001a-rt10 | Bluefin Hospital, BFH        | Amstelveen, Rotterdam, Gorinchem, Eindhoven |
| gen-308              | NWR SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt07                                           | Northwind Research, NWR      | Maastricht |
| gen-309              | BFU SP TAGGED ASV002A 10 Gbit/s                | asv002a-rt06                                           | Bluefin University, BFU      | Amstelveen |
| gen-311              | BFH LP EHV001A-UTR002A 10 Gbit/s               | utr002a-rt08, ehv001a-rt07                             | Bluefin Hospital, BFH        | Utrecht, Eindhoven |
| gen-313              | GFO SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt10                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-314              | BFH IP GRQ001A 10 Gbit/s                       | grq001a-rt02                                           | Bluefin Hospital, BFH        | Groningen |
| gen-315              | RWI LP ENS001A-UTR002A 100 Gbit/s              | utr002a-rt03, ens001a-rt11                             | Redwood Institute, RWI       | Utrecht, Enschede |
| gen-316              | GFO LP ASV001A-RTD001A 1 Gbit/s                | asv001a-rt08, rtd001a-rt04                             | Greenfield Observatory, GFO  | Amstelveen, Rotterdam |
| gen-318              | BFH IP EHV002A 100 Gbit/s                      | ehv002a-rt02                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-319              | NWL SP TAGGED RMD001A 1 Gbit/s                 | rmd001a-rt06                                           | Northwind Labs, NWL          | Roermond |
| gen-320              | BFH SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt04                                           | Bluefin Hospital, BFH        | Almere |
| gen-322              | NWR LP ALM001A-GRQ001A 100 Gbit/s              | grq001a-rt11, alm001a-rt02                             | Northwind Research, NWR      | Groningen, Almere |
| gen-323              | GFO L2VPN AMS002A-EHV001A-ENS001A 10 Gbit/s    | ehv001a-rt02, ens001a-rt01, ams002a-rt01               | Greenfield Observatory, GFO  | Eindhoven, Enschede, Amsterdam |
| gen-329              | RWI LP GOR002A-RTD001A 1 Gbit/s                | gor002a-rt07, rtd001a-rt02                             | Redwood Institute, RWI       | Gorinchem, Rotterdam |
| gen-331              | BFU SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt03                                           | Bluefin University, BFU      | Enschede |
| gen-332              | NWR SP TAGGED ENS001A 10 Gbit/s                | ens001a-rt10                                           | Northwind Research, NWR      | Enschede |
| gen-334              | RWI IP GOR001A 1 Gbit/s                        | gor001a-rt12                                           | Redwood Institute, RWI       | Gorinchem |
| gen-335              | SLA IP GOR001A 10 Gbit/s                       | gor001a-rt07                                           | Silverline Archives, SLA     | Gorinchem |
| gen-336              | BFU IP ARN002A 100 Gbit/s                      | arn002a-rt05                                           | Bluefin University, BFU      | Arnhem |
| gen-339              | NWR SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt04                                           | Northwind Research, NWR      | Groningen |
| gen-340              | RWI L2VPN ARN002A-RTD002A 1 Gbit/s             | arn002a-rt12, rtd002a-rt04                             | Redwood Institute, RWI       | Arnhem, Rotterdam |
| gen-341              | BFU LP ARN002A-EHV002A 100 Gbit/s              | arn002a-rt12, ehv002a-rt12                             | Bluefin University, BFU      | Arnhem, Eindhoven |
| gen-344              | RWL SP UNTAGGED AMS001A 1 Gbit/s               | ams001a-rt03                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-345              | RWL SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt12                                           | Redwood Libraries, RWL       | Enschede |
| gen-346              | GFO SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt02                                           | Greenfield Observatory, GFO  | Enschede |
| gen-347              | BFU LP ALM001A-GRQ002A 1 Gbit/s                | alm001a-rt12, grq002a-rt04                             | Bluefin University, BFU      | Almere, Groningen |
| gen-349              | RWL LP MST001A-UTR001A 1 Gbit/s                | mst001a-rt12, utr001a-rt12                             | Redwood Libraries, RWL       | Maastricht, Utrecht |
| gen-350              | NWL IP GOR002A 1 Gbit/s                        | gor002a-rt07                                           | Northwind Labs, NWL          | Gorinchem |
| gen-351              | GFC LP EHV001A-UTR001A 1 Gbit/s                | utr001a-rt01, ehv001a-rt07                             | Greenfield College, GFC      | Utrecht, Eindhoven |
| gen-353              | SLA IP UTR002A 10 Gbit/s                       | utr002a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-354              | GFO L2VPN AMS002A-ARN002A-ENS001A 100 Gbit/s   | ams002a-rt11, arn002a-rt03, ens001a-rt07               | Greenfield Observatory, GFO  | Amsterdam, Arnhem, Enschede |
| gen-355              | GFC IP UTR001A 10 Gbit/s                       | utr001a-rt06                                           | Greenfield College, GFC      | Utrecht |
| gen-356              | NWL LP EHV002A-GOR001A 10 Gbit/s               | ehv002a-rt08, gor001a-rt03                             | Northwind Labs, NWL          | Eindhoven, Gorinchem |
| gen-357              | GFO LP EHV002A-RTD002A 1 Gbit/s                | ehv002a-rt07, rtd002a-rt10                             | Greenfield Observatory, GFO  | Eindhoven, Rotterdam |
| gen-359              | RWI IP EHV002A 100 Gbit/s                      | ehv002a-rt10                                           | Redwood Institute, RWI       | Eindhoven |
| gen-361              | RWI LP ARN002A-GOR001A 100 Gbit/s              | gor001a-rt10, arn002a-rt04                             | Redwood Institute, RWI       | Gorinchem, Arnhem |
| gen-362              | GFC LP ALM002A-AMS001A 100 Gbit/s              | ams001a-rt03, alm002a-rt07                             | Greenfield College, GFC      | Amsterdam, Almere |
| gen-363              | RWL IP EHV001A 1 Gbit/s                        | ehv001a-rt08                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-366              | RWL LP ALM002A-ARN002A 100 Gbit/s              | alm002a-rt05, arn002a-rt10                             | Redwood Libraries, RWL       | Almere, Arnhem |
| gen-367              | BFH SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt12                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-368              | NWL SP TAGGED MST002A 10 Gbit/s                | mst002a-rt07                                           | Northwind Labs, NWL          | Maastricht |
| gen-371              | SLM IP AMS001A 1 Gbit/s                        | ams001a-rt05                                           | Silverline Museum, SLM       | Amsterdam |
| gen-372              | BFU SP TAGGED UTR002A 100 Gbit/s               | utr002a-rt02                                           | Bluefin University, BFU      | Utrecht |
| gen-373              | GFO LP ALM002A-GOR001A 10 Gbit/s               | gor001a-rt08, alm002a-rt05                             | Greenfield Observatory, GFO  | Gorinchem, Almere |
| gen-374              | BFU L2VPN ARN002A-UTR002A 100 Gbit/s           | arn002a-rt05, utr002a-rt03                             | Bluefin University, BFU      | Arnhem, Utrecht |
| gen-376              | SLA IP ASV002A 100 Gbit/s                      | asv002a-rt04                                           | Silverline Archives, SLA     | Amstelveen |
| gen-377              | RWI SP UNTAGGED RTD001A 100 Gbit/s             | rtd001a-rt08                                           | Redwood Institute, RWI       | Rotterdam |
| gen-378              | GFO L2VPN ASV002A-GRQ001A-RTD001A 10 Gbit/s    | rtd001a-rt11, grq001a-rt02, asv002a-rt11               | Greenfield Observatory, GFO  | Rotterdam, Groningen, Amstelveen |
| gen-380              | SLM LP AMS002A-GRQ001A 10 Gbit/s               | ams002a-rt05, grq001a-rt02                             | Silverline Museum, SLM       | Amsterdam, Groningen |
| gen-382              | NWR SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt05                                           | Northwind Research, NWR      | Gorinchem |
| gen-383              | NWL L2VPN EHV002A-ENS002A-GRQ001A 100 Gbit/s   | grq001a-rt10, ehv002a-rt01, ens002a-rt04, grq001a-rt03 | Northwind Labs, NWL          | Groningen, Eindhoven, Enschede |
| gen-386              | RWI IP AMS002A 10 Gbit/s                       | ams002a-rt10                                           | Redwood Institute, RWI       | Amsterdam |
| gen-388              | BFU IP ARN001A 10 Gbit/s                       | arn001a-rt05                                           | Bluefin University, BFU      | Arnhem |
| gen-389              | BFH SP TAGGED UTR001A 100 Gbit/s               | utr001a-rt06                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-390              | BFU LP GOR002A-RMD001A 10 Gbit/s               | rmd001a-rt08, gor002a-rt05                             | Bluefin University, BFU      | Roermond, Gorinchem |
| gen-393              | BFU L2VPN ALM002A-MST001A-UTR002A 1 Gbit/s     | alm002a-rt08, mst001a-rt11, utr002a-rt03               | Bluefin University, BFU      | Almere, Maastricht, Utrecht |
| gen-394              | NWR IP ARN002A 1 Gbit/s                        | arn002a-rt02                                           | Northwind Research, NWR      | Arnhem |
| gen-398              | BFU L2VPN EHV002A-UTR001A 1 Gbit/s             | utr001a-rt06, ehv002a-rt01                             | Bluefin University, BFU      | Utrecht, Eindhoven |
| gen-400              | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt05                                           | Greenfield College, GFC      | Enschede |
| gen-401              | NWR L2VPN ALM002A-GOR001A 100 Gbit/s           | gor001a-rt08, alm002a-rt08                             | Northwind Research, NWR      | Gorinchem, Almere |
| gen-403              | BFU SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt07                                           | Bluefin University, BFU      | Amstelveen |
| gen-404              | BFU LP EHV002A-MST002A 1 Gbit/s                | ehv002a-rt10, mst002a-rt07                             | Bluefin University, BFU      | Eindhoven, Maastricht |
| gen-405              | GFO SP TAGGED EHV002A 10 Gbit/s                | ehv002a-rt01                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-409              | BFH SP TAGGED GRQ002A 10 Gbit/s                | grq002a-rt12                                           | Bluefin Hospital, BFH        | Groningen |
| gen-410              | RWL SP UNTAGGED ENS002A 100 Gbit/s             | ens002a-rt06                                           | Redwood Libraries, RWL       | Enschede |
| gen-411              | GFO IP RTD001A 10 Gbit/s                       | rtd001a-rt09                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-412              | GFO SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt06                                           | Greenfield Observatory, GFO  | Groningen |
| gen-414              | GFO SP UNTAGGED ASV002A 10 Gbit/s              | asv002a-rt01                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-415              | RWL IP EHV001A 1 Gbit/s                        | ehv001a-rt10                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-420              | BFH L2VPN ARN002A-EHV002A-ENS002A 100 Gbit/s   | arn002a-rt02, rtd002a-rt10, ehv002a-rt02, ens002a-rt04 | Bluefin Hospital, BFH        | Arnhem, Rotterdam, Eindhoven, Enschede |
| gen-421              | NWR LP EHV001A-GOR001A 1 Gbit/s                | gor001a-rt06, ehv001a-rt07                             | Northwind Research, NWR      | Gorinchem, Eindhoven |
| gen-423              | NWR IP GOR002A 10 Gbit/s                       | gor002a-rt10                                           | Northwind Research, NWR      | Gorinchem |
| gen-424              | GFO LP ASV001A-EHV002A 100 Gbit/s              | ehv002a-rt12, asv001a-rt09                             | Greenfield Observatory, GFO  | Eindhoven, Amstelveen |
| gen-425              | SLA IP GOR002A 100 Gbit/s                      | gor002a-rt07                                           | Silverline Archives, SLA     | Gorinchem |
| gen-426              | SLM L2VPN ASV002A-GOR001A 100 Gbit/s           | gor001a-rt12, asv002a-rt01                             | Silverline Museum, SLM       | Gorinchem, Amstelveen |
| gen-429              | SLM L2VPN ASV001A-GRQ002A 1 Gbit/s             | asv001a-rt05, grq002a-rt07                             | Silverline Museum, SLM       | Amstelveen, Groningen |
| gen-430              | SLA LP AMS001A-ASV001A 10 Gbit/s               | asv001a-rt11, ams001a-rt03                             | Silverline Archives, SLA     | Amstelveen, Amsterdam |
| gen-433              | RWI SP TAGGED MST001A 1 Gbit/s                 | mst001a-rt07                                           | Redwood Institute, RWI       | Maastricht |
| gen-435              | RWL IP AMS002A 100 Gbit/s                      | ams002a-rt02                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-437              | RWL IP ALM002A 1 Gbit/s                        | alm002a-rt06                                           | Redwood Libraries, RWL       | Almere |
| gen-439              | RWI IP ARN001A 100 Gbit/s                      | arn001a-rt04                                           | Redwood Institute, RWI       | Arnhem |
| gen-440              | BFU LP ARN001A-GRQ001A 1 Gbit/s                | arn001a-rt12, grq001a-rt02                             | Bluefin University, BFU      | Arnhem, Groningen |
| gen-441              | BFU SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt08                                           | Bluefin University, BFU      | Maastricht |
| gen-442              | GFO L2VPN ARN001A-ASV001A-GRQ002A 1 Gbit/s     | asv001a-rt10, arn001a-rt12, grq002a-rt05               | Greenfield Observatory, GFO  | Amstelveen, Arnhem, Groningen |
| gen-443              | NWL IP GRQ001A 10 Gbit/s                       | grq001a-rt11                                           | Northwind Labs, NWL          | Groningen |
| gen-444              | BFU IP ALM002A 1 Gbit/s                        | alm002a-rt04                                           | Bluefin University, BFU      | Almere |
| gen-447              | GFO LP ENS001A-RTD002A 100 Gbit/s              | rtd002a-rt07, ens001a-rt01                             | Greenfield Observatory, GFO  | Rotterdam, Enschede |
| gen-448              | SLM IP AMS002A 100 Gbit/s                      | ams002a-rt03                                           | Silverline Museum, SLM       | Amsterdam |
| gen-449              | RWI L2VPN ENS001A-ENS002A-MST002A 1 Gbit/s     | mst002a-rt04, utr001a-rt08, ens002a-rt09, ens001a-rt12 | Redwood Institute, RWI       | Maastricht, Utrecht, Enschede |
| gen-451              | NWL IP ALM002A 100 Gbit/s                      | alm002a-rt12                                           | Northwind Labs, NWL          | Almere |
| gen-452              | RWL LP ARN002A-RMD002A 10 Gbit/s               | arn002a-rt07, rmd002a-rt11                             | Redwood Libraries, RWL       | Arnhem, Roermond |
| gen-453              | GFO SP TAGGED RTD001A 1 Gbit/s                 | rtd001a-rt02                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-454              | SLA SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt09                                           | Silverline Archives, SLA     | Almere |
| gen-455              | GFC IP UTR002A 1 Gbit/s                        | utr002a-rt04                                           | Greenfield College, GFC      | Utrecht |
| gen-456              | BFH IP UTR001A 1 Gbit/s                        | utr001a-rt04                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-457              | GFC IP RMD001A 10 Gbit/s                       | rmd001a-rt08                                           | Greenfield College, GFC      | Roermond |
| gen-459              | RWI SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt06                                           | Redwood Institute, RWI       | Maastricht |
| gen-460              | GFC SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt03                                           | Greenfield College, GFC      | Groningen |
| gen-461              | RWI LP ARN002A-RTD002A 10 Gbit/s               | rtd002a-rt05, arn002a-rt12                             | Redwood Institute, RWI       | Rotterdam, Arnhem |
| gen-462              | BFH IP GRQ002A 1 Gbit/s                        | grq002a-rt07                                           | Bluefin Hospital, BFH        | Groningen |
| gen-463              | NWR LP ASV001A-MST002A 10 Gbit/s               | mst002a-rt12, asv001a-rt08                             | Northwind Research, NWR      | Maastricht, Amstelveen |
| gen-465              | NWL SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt06                                           | Northwind Labs, NWL          | Amstelveen |
| gen-466              | SLM IP GOR001A 1 Gbit/s                        | gor001a-rt08                                           | Silverline Museum, SLM       | Gorinchem |
| gen-467              | SLM SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt04                                           | Silverline Museum, SLM       | Arnhem |
| gen-470              | RWI SP TAGGED ENS002A 100 Gbit/s               | ens002a-rt01                                           | Redwood Institute, RWI       | Enschede |
| gen-471              | GFO SP UNTAGGED GOR002A 1 Gbit/s               | gor002a-rt08                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-474              | BFU L2VPN ALM001A-ARN001A-GRQ002A 10 Gbit/s    | arn001a-rt04, grq002a-rt03, alm001a-rt11               | Bluefin University, BFU      | Arnhem, Groningen, Almere |
| gen-476              | SLA SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt02                                           | Silverline Archives, SLA     | Utrecht |
| gen-478              | SLA L2VPN ALM002A-UTR002A 10 Gbit/s            | alm002a-rt09, utr002a-rt08                             | Silverline Archives, SLA     | Almere, Utrecht |
| gen-479              | RWL SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt09                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-481              | SLM SP UNTAGGED UTR002A 1 Gbit/s               | utr002a-rt03                                           | Silverline Museum, SLM       | Utrecht |
| gen-482              | NWR L2VPN GOR001A 1 Gbit/s                     | gor001a-rt02, gor001a-rt12                             | Northwind Research, NWR      | Gorinchem |
| gen-483              | NWR LP ALM002A-EHV001A 10 Gbit/s               | ehv001a-rt01, alm002a-rt01                             | Northwind Research, NWR      | Eindhoven, Almere |
| gen-484              | SLM L2VPN AMS002A-GRQ002A 100 Gbit/s           | ams002a-rt01, grq002a-rt08                             | Silverline Museum, SLM       | Amsterdam, Groningen |
| gen-486              | BFU LP ARN001A-GOR002A 10 Gbit/s               | arn001a-rt08, gor002a-rt09                             | Bluefin University, BFU      | Arnhem, Gorinchem |
| gen-487              | GFO LP ARN002A-ASV001A 1 Gbit/s                | arn002a-rt02, asv001a-rt11                             | Greenfield Observatory, GFO  | Arnhem, Amstelveen |
| gen-488              | GFO SP UNTAGGED RTD002A 100 Gbit/s             | rtd002a-rt02                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-489              | GFO LP ALM001A-ENS002A 1 Gbit/s                | ens002a-rt03, alm001a-rt01                             | Greenfield Observatory, GFO  | Enschede, Almere |
| gen-490              | RWI LP GOR002A-GOR002A 10 Gbit/s               | gor002a-rt04, gor002a-rt03                             | Redwood Institute, RWI       | Gorinchem |
| gen-491              | GFO IP ARN001A 10 Gbit/s                       | arn001a-rt07                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-492              | NWL L2VPN ASV002A-GOR001A-GRQ001A 1 Gbit/s     | mst001a-rt12, grq001a-rt05, asv002a-rt08, gor001a-rt11 | Northwind Labs, NWL          | Maastricht, Groningen, Amstelveen, Gorinchem |
| gen-495              | GFC SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt01                                           | Greenfield College, GFC      | Almere |
| gen-497              | RWL LP ALM001A-GRQ002A 1 Gbit/s                | grq002a-rt09, alm001a-rt06                             | Redwood Libraries, RWL       | Groningen, Almere |
| gen-499              | RWL SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt04                                           | Redwood Libraries, RWL       | Roermond |
| gen-500              | NWR IP ASV002A 100 Gbit/s                      | asv002a-rt08                                           | Northwind Research, NWR      | Amstelveen |
| gen-502              | SLA L2VPN ASV002A-GRQ001A 10 Gbit/s            | grq001a-rt05, asv002a-rt03                             | Silverline Archives, SLA     | Groningen, Amstelveen |
| gen-503              | SLM L2VPN GRQ002A-MST001A 100 Gbit/s           | grq002a-rt10, mst001a-rt01                             | Silverline Museum, SLM       | Groningen, Maastricht |
| gen-504              | NWR IP GRQ002A 100 Gbit/s                      | grq002a-rt07                                           | Northwind Research, NWR      | Groningen |
| gen-505              | NWR L2VPN ALM001A-ARN001A 10 Gbit/s            | arn001a-rt01, alm001a-rt11                             | Northwind Research, NWR      | Arnhem, Almere |
| gen-506              | NWL IP MST001A 1 Gbit/s                        | mst001a-rt07                                           | Northwind Labs, NWL          | Maastricht |
| gen-507              | GFO SP TAGGED RTD001A 100 Gbit/s               | rtd001a-rt10                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-508              | NWR IP GRQ002A 10 Gbit/s                       | grq002a-rt02                                           | Northwind Research, NWR      | Groningen |
| gen-509              | GFO LP ENS002A-RTD002A 100 Gbit/s              | ens002a-rt04, rtd002a-rt09                             | Greenfield Observatory, GFO  | Enschede, Rotterdam |
| gen-512              | NWR L2VPN ARN001A-GOR002A 1 Gbit/s             | gor002a-rt11, arn001a-rt11                             | Northwind Research, NWR      | Gorinchem, Arnhem |
| gen-513              | RWI IP GOR001A 10 Gbit/s                       | gor001a-rt09                                           | Redwood Institute, RWI       | Gorinchem |
| gen-515              | RWI IP ENS001A 10 Gbit/s                       | ens001a-rt10                                           | Redwood Institute, RWI       | Enschede |
| gen-518              | SLA LP AMS002A-ARN002A 10 Gbit/s               | arn002a-rt01, ams002a-rt04                             | Silverline Archives, SLA     | Arnhem, Amsterdam |
| gen-520              | GFC L2VPN ASV001A-UTR001A 10 Gbit/s            | utr001a-rt11, asv001a-rt12                             | Greenfield College, GFC      | Utrecht, Amstelveen |
| gen-521              | NWL SP TAGGED RMD002A 100 Gbit/s               | rmd002a-rt05                                           | Northwind Labs, NWL          | Roermond |
| gen-523              | GFC IP ARN001A 100 Gbit/s                      | arn001a-rt08                                           | Greenfield College, GFC      | Arnhem |
| gen-524              | GFO LP AMS002A-UTR002A 10 Gbit/s               | ams002a-rt07, utr002a-rt01                             | Greenfield Observatory, GFO  | Amsterdam, Utrecht |
| gen-525              | RWL IP ALM001A 10 Gbit/s                       | alm001a-rt08                                           | Redwood Libraries, RWL       | Almere |
| gen-526              | BFU IP GRQ001A 1 Gbit/s                        | grq001a-rt02                                           | Bluefin University, BFU      | Groningen |
| gen-527              | BFU LP EHV002A-GOR002A 10 Gbit/s               | gor002a-rt01, ehv002a-rt11                             | Bluefin University, BFU      | Gorinchem, Eindhoven |
| gen-528              | GFO IP EHV002A 10 Gbit/s                       | ehv002a-rt11                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-529              | BFH IP ARN001A 1 Gbit/s                        | arn001a-rt05                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-532              | NWR IP RMD001A 100 Gbit/s                      | rmd001a-rt09                                           | Northwind Research, NWR      | Roermond |
| gen-533              | RWI SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt08                                           | Redwood Institute, RWI       | Groningen |
| gen-534              | RWL LP ALM002A-MST001A 1 Gbit/s                | alm002a-rt12, mst001a-rt02                             | Redwood Libraries, RWL       | Almere, Maastricht |
| gen-540              | GFO IP RTD001A 10 Gbit/s                       | rtd001a-rt06                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-541              | BFU SP UNTAGGED UTR002A 100 Gbit/s             | utr002a-rt09                                           | Bluefin University, BFU      | Utrecht |
| gen-542              | BFH LP RMD002A-RMD002A 1 Gbit/s                | rmd002a-rt09, rmd002a-rt07                             | Bluefin Hospital, BFH        | Roermond |
| gen-544              | BFU LP ARN001A-GOR001A 10 Gbit/s               | gor001a-rt06, arn001a-rt09                             | Bluefin University, BFU      | Gorinchem, Arnhem |
| gen-545              | NWR IP ENS002A 10 Gbit/s                       | ens002a-rt08                                           | Northwind Research, NWR      | Enschede |
| gen-546              | NWL LP EHV002A-RMD002A 10 Gbit/s               | rmd002a-rt01, ehv002a-rt03                             | Northwind Labs, NWL          | Roermond, Eindhoven |
| gen-548              | NWR L2VPN ALM001A-ENS002A-GOR002A 100 Gbit/s   | ens002a-rt08, alm001a-rt03, alm001a-rt11, gor002a-rt05 | Northwind Research, NWR      | Enschede, Almere, Gorinchem |
| gen-549              | BFU IP GRQ001A 100 Gbit/s                      | grq001a-rt01                                           | Bluefin University, BFU      | Groningen |
| gen-550              | RWI IP UTR001A 100 Gbit/s                      | utr001a-rt08                                           | Redwood Institute, RWI       | Utrecht |
| gen-551              | SLM SP TAGGED ASV002A 1 Gbit/s                 | asv002a-rt01                                           | Silverline Museum, SLM       | Amstelveen |
| gen-552              | RWI LP EHV001A-GOR001A 100 Gbit/s              | ehv001a-rt09, gor001a-rt12                             | Redwood Institute, RWI       | Eindhoven, Gorinchem |
| gen-555              | GFC L2VPN ALM002A-AMS002A-ARN001A 10 Gbit/s    | ams002a-rt10, arn001a-rt02, alm002a-rt06, mst002a-rt01 | Greenfield College, GFC      | Amsterdam, Arnhem, Almere, Maastricht |
| gen-556              | BFH L2VPN ALM002A-MST001A-RMD002A 100 Gbit/s   | mst001a-rt08, rmd002a-rt03, alm002a-rt05               | Bluefin Hospital, BFH        | Maastricht, Roermond, Almere |
| gen-557              | BFH SP TAGGED UTR002A 1 Gbit/s                 | utr002a-rt01                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-559              | RWL LP ALM002A-ARN002A 1 Gbit/s                | alm002a-rt03, arn002a-rt09                             | Redwood Libraries, RWL       | Almere, Arnhem |
| gen-560              | BFH IP ENS002A 1 Gbit/s                        | ens002a-rt05                                           | Bluefin Hospital, BFH        | Enschede |
| gen-562              | SLA L2VPN ALM001A-AMS001A-ASV002A 10 Gbit/s    | alm001a-rt06, gor002a-rt07, ams001a-rt03, asv002a-rt08 | Silverline Archives, SLA     | Almere, Gorinchem, Amsterdam, Amstelveen |
| gen-563              | SLA SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt07                                           | Silverline Archives, SLA     | Arnhem |
| gen-564              | BFH LP EHV002A-ENS001A 1 Gbit/s                | ehv002a-rt10, ens001a-rt01                             | Bluefin Hospital, BFH        | Eindhoven, Enschede |
| gen-565              | RWL SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt05                                           | Redwood Libraries, RWL       | Almere |
| gen-566              | BFU LP GOR001A-RTD001A 10 Gbit/s               | rtd001a-rt02, gor001a-rt09                             | Bluefin University, BFU      | Rotterdam, Gorinchem |
| gen-567              | RWI LP ARN001A-UTR001A 100 Gbit/s              | utr001a-rt07, arn001a-rt06                             | Redwood Institute, RWI       | Utrecht, Arnhem |
| gen-570              | SLA LP GRQ001A-GRQ001A 100 Gbit/s              | grq001a-rt10, grq001a-rt01                             | Silverline Archives, SLA     | Groningen |
| gen-574              | RWL SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt09                                           | Redwood Libraries, RWL       | Maastricht |
| gen-576              | BFU L2VPN ALM002A-ENS002A 100 Gbit/s           | alm002a-rt04, ens002a-rt06                             | Bluefin University, BFU      | Almere, Enschede |
| gen-578              | BFH LP GOR001A-MST002A 100 Gbit/s              | mst002a-rt04, gor001a-rt09                             | Bluefin Hospital, BFH        | Maastricht, Gorinchem |
| gen-579              | NWL L2VPN EHV001A-ENS001A 100 Gbit/s           | ehv001a-rt09, ens001a-rt10                             | Northwind Labs, NWL          | Eindhoven, Enschede |
| gen-580              | NWR SP TAGGED RMD002A 1 Gbit/s                 | rmd002a-rt12                                           | Northwind Research, NWR      | Roermond |
| gen-581              | NWL SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt07                                           | Northwind Labs, NWL          | Amstelveen |
| gen-582              | RWL SP TAGGED ENS002A 100 Gbit/s               | ens002a-rt06                                           | Redwood Libraries, RWL       | Enschede |
| gen-583              | NWL IP ENS002A 100 Gbit/s                      | ens002a-rt12                                           | Northwind Labs, NWL          | Enschede |
| gen-584              | NWL SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt04                                           | Northwind Labs, NWL          | Arnhem |
| gen-585              | GFC LP ENS002A-RMD001A 10 Gbit/s               | ens002a-rt08, rmd001a-rt10                             | Greenfield College, GFC      | Enschede, Roermond |
| gen-586              | BFU L2VPN ALM001A-GOR002A-RMD001A 100 Gbit/s   | alm001a-rt11, gor002a-rt02, rmd001a-rt10               | Bluefin University, BFU      | Almere, Gorinchem, Roermond |
| gen-588              | BFU L2VPN GRQ002A-MST002A 10 Gbit/s            | grq002a-rt09, mst002a-rt10                             | Bluefin University, BFU      | Groningen, Maastricht |
| gen-589              | NWR LP ASV002A-ENS001A 1 Gbit/s                | ens001a-rt04, asv002a-rt11                             | Northwind Research, NWR      | Enschede, Amstelveen |
| gen-590              | SLA IP ALM002A 100 Gbit/s                      | alm002a-rt03                                           | Silverline Archives, SLA     | Almere |
| gen-591              | GFC SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt08                                           | Greenfield College, GFC      | Groningen |
| gen-594              | NWR L2VPN GRQ002A-MST001A 100 Gbit/s           | mst001a-rt12, grq002a-rt02                             | Northwind Research, NWR      | Maastricht, Groningen |
| gen-596              | GFO L2VPN AMS001A-GRQ002A-RMD001A 10 Gbit/s    | rmd001a-rt03, grq002a-rt11, ams001a-rt06               | Greenfield Observatory, GFO  | Roermond, Groningen, Amsterdam |
| gen-597              | NWR L2VPN ARN002A-ASV002A-GRQ001A 10 Gbit/s    | grq001a-rt07, asv002a-rt12, arn002a-rt05               | Northwind Research, NWR      | Groningen, Amstelveen, Arnhem |
| gen-598              | SLA SP UNTAGGED GOR002A 1 Gbit/s               | gor002a-rt06                                           | Silverline Archives, SLA     | Gorinchem |
| gen-599              | RWI IP GOR002A 1 Gbit/s                        | gor002a-rt10                                           | Redwood Institute, RWI       | Gorinchem |
| gen-600              | BFH IP GRQ001A 10 Gbit/s                       | grq001a-rt09                                           | Bluefin Hospital, BFH        | Groningen |
| gen-601              | RWI IP MST002A 100 Gbit/s                      | mst002a-rt11                                           | Redwood Institute, RWI       | Maastricht |
| gen-603              | NWL L2VPN ALM001A-MST002A 10 Gbit/s            | mst002a-rt04, alm001a-rt01                             | Northwind Labs, NWL          | Maastricht, Almere |
| gen-605              | SLM L2VPN AMS002A-ARN001A 100 Gbit/s           | arn001a-rt06, ams002a-rt10                             | Silverline Museum, SLM       | Arnhem, Amsterdam |
| gen-606              | NWL IP RMD002A 10 Gbit/s                       | rmd002a-rt06                                           | Northwind Labs, NWL          | Roermond |
| gen-607              | RWL SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-608              | GFO IP GRQ001A 10 Gbit/s                       | grq001a-rt04                                           | Greenfield Observatory, GFO  | Groningen |
| gen-610              | BFU SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt09                                           | Bluefin University, BFU      | Utrecht |
| gen-611              | GFC SP UNTAGGED RTD001A 10 Gbit/s              | rtd001a-rt02                                           | Greenfield College, GFC      | Rotterdam |
| gen-612              | GFC L2VPN ARN002A-GOR002A-GRQ002A 10 Gbit/s    | grq002a-rt08, arn002a-rt10, gor002a-rt10               | Greenfield College, GFC      | Groningen, Arnhem, Gorinchem |
| gen-613              | RWI SP TAGGED UTR001A 10 Gbit/s                | utr001a-rt08                                           | Redwood Institute, RWI       | Utrecht |
| gen-614              | RWL L2VPN ALM002A-EHV001A-RTD002A 1 Gbit/s     | rtd002a-rt05, alm002a-rt06, ehv001a-rt06               | Redwood Libraries, RWL       | Rotterdam, Almere, Eindhoven |
| gen-616              | RWI L2VPN ARN002A-MST002A-RMD001A 10 Gbit/s    | mst002a-rt08, rmd001a-rt06, rmd002a-rt01, arn002a-rt05 | Redwood Institute, RWI       | Maastricht, Roermond, Arnhem |
| gen-617              | BFH LP ALM002A-GRQ001A 10 Gbit/s               | grq001a-rt06, alm002a-rt05                             | Bluefin Hospital, BFH        | Groningen, Almere |
| gen-618              | RWI LP ENS001A-MST002A 10 Gbit/s               | mst002a-rt07, ens001a-rt05                             | Redwood Institute, RWI       | Maastricht, Enschede |
| gen-624              | SLA IP GOR001A 1 Gbit/s                        | gor001a-rt12                                           | Silverline Archives, SLA     | Gorinchem |
| gen-626              | RWI IP ARN002A 10 Gbit/s                       | arn002a-rt07                                           | Redwood Institute, RWI       | Arnhem |
| gen-627              | BFH SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt08                                           | Bluefin Hospital, BFH        | Enschede |
| gen-630              | RWL L2VPN ARN001A-ENS002A-GRQ001A 10 Gbit/s    | grq001a-rt11, ens002a-rt07, arn001a-rt06, rmd001a-rt12 | Redwood Libraries, RWL       | Groningen, Enschede, Arnhem, Roermond |
| gen-632              | NWR IP ARN002A 1 Gbit/s                        | arn002a-rt01                                           | Northwind Research, NWR      | Arnhem |
| gen-634              | RWI SP TAGGED GRQ002A 1 Gbit/s                 | grq002a-rt04                                           | Redwood Institute, RWI       | Groningen |
| gen-635              | BFU L2VPN EHV002A-RMD002A 100 Gbit/s           | ehv002a-rt08, rmd002a-rt05                             | Bluefin University, BFU      | Eindhoven, Roermond |
| gen-636              | GFO LP ENS001A-RTD001A 100 Gbit/s              | rtd001a-rt02, ens001a-rt06                             | Greenfield Observatory, GFO  | Rotterdam, Enschede |
| gen-638              | NWL IP EHV002A 100 Gbit/s                      | ehv002a-rt02                                           | Northwind Labs, NWL          | Eindhoven |
| gen-639              | GFO SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt04                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-640              | RWL L2VPN RMD002A-UTR001A 1 Gbit/s             | utr001a-rt01, rmd002a-rt07                             | Redwood Libraries, RWL       | Utrecht, Roermond |
| gen-642              | SLA IP GOR002A 10 Gbit/s                       | gor002a-rt07                                           | Silverline Archives, SLA     | Gorinchem |
| gen-647              | RWI IP ALM001A 1 Gbit/s                        | alm001a-rt06                                           | Redwood Institute, RWI       | Almere |
| gen-648              | BFU IP RMD002A 1 Gbit/s                        | rmd002a-rt07                                           | Bluefin University, BFU      | Roermond |
| gen-649              | BFU SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt06                                           | Bluefin University, BFU      | Maastricht |
| gen-650              | RWL L2VPN GOR001A-MST001A-RTD001A 1 Gbit/s     | mst001a-rt01, gor001a-rt08, rtd001a-rt11               | Redwood Libraries, RWL       | Maastricht, Gorinchem, Rotterdam |
| gen-651              | SLA IP GRQ002A 10 Gbit/s                       | grq002a-rt09                                           | Silverline Archives, SLA     | Groningen |
| gen-653              | RWL L2VPN AMS002A-EHV002A-ENS002A 100 Gbit/s   | ehv002a-rt11, ens002a-rt11, ams002a-rt09               | Redwood Libraries, RWL       | Eindhoven, Enschede, Amsterdam |
| gen-654              | SLM LP GOR001A-GOR002A 100 Gbit/s              | gor002a-rt03, gor001a-rt11                             | Silverline Museum, SLM       | Gorinchem |
| gen-655              | RWI IP UTR002A 100 Gbit/s                      | utr002a-rt03                                           | Redwood Institute, RWI       | Utrecht |
| gen-656              | RWL IP RMD001A 100 Gbit/s                      | rmd001a-rt03                                           | Redwood Libraries, RWL       | Roermond |
| gen-658              | GFC IP UTR001A 1 Gbit/s                        | utr001a-rt07                                           | Greenfield College, GFC      | Utrecht |
| gen-660              | BFU LP ENS001A-MST002A 1 Gbit/s                | ens001a-rt06, mst002a-rt01                             | Bluefin University, BFU      | Enschede, Maastricht |
| gen-662              | GFO IP RTD002A 1 Gbit/s                        | rtd002a-rt09                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-663              | GFO LP ALM001A-GRQ002A 1 Gbit/s                | grq002a-rt07, alm001a-rt01                             | Greenfield Observatory, GFO  | Groningen, Almere |
| gen-664              | GFC IP RTD001A 10 Gbit/s                       | rtd001a-rt12                                           | Greenfield College, GFC      | Rotterdam |
| gen-665              | BFH IP RMD001A 10 Gbit/s                       | rmd001a-rt07                                           | Bluefin Hospital, BFH        | Roermond |
| gen-666              | RWI LP RMD001A-RTD002A 1 Gbit/s                | rtd002a-rt09, rmd001a-rt09                             | Redwood Institute, RWI       | Rotterdam, Roermond |
| gen-667              | BFH IP EHV001A 10 Gbit/s                       | ehv001a-rt04                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-668              | BFH IP RMD001A 1 Gbit/s                        | rmd001a-rt05                                           | Bluefin Hospital, BFH        | Roermond |
| gen-670              | GFO L2VPN ALM001A-ARN002A 100 Gbit/s           | alm001a-rt03, arn002a-rt12                             | Greenfield Observatory, GFO  | Almere, Arnhem |
| gen-671              | RWL LP ARN002A-GOR002A 100 Gbit/s              | gor002a-rt02, arn002a-rt08                             | Redwood Libraries, RWL       | Gorinchem, Arnhem |
| gen-673              | NWR SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt11                                           | Northwind Research, NWR      | Arnhem |
| gen-674              | GFC LP AMS001A-ASV001A 100 Gbit/s              | ams001a-rt08, asv001a-rt02                             | Greenfield College, GFC      | Amsterdam, Amstelveen |
| gen-675              | BFH L2VPN ASV001A-EHV002A-ENS002A 10 Gbit/s    | ens002a-rt09, ehv002a-rt02, gor002a-rt12, asv001a-rt12 | Bluefin Hospital, BFH        | Enschede, Eindhoven, Gorinchem, Amstelveen |
| gen-676              | RWI L2VPN ENS002A-MST002A-RMD002A 1 Gbit/s     | ens002a-rt12, mst002a-rt09, rmd002a-rt12               | Redwood Institute, RWI       | Enschede, Maastricht, Roermond |
| gen-678              | BFU L2VPN ENS002A-GOR002A-MST001A 1 Gbit/s     | ens002a-rt05, gor002a-rt06, rtd001a-rt04, mst001a-rt07 | Bluefin University, BFU      | Enschede, Gorinchem, Rotterdam, Maastricht |
| gen-679              | NWL IP GRQ002A 100 Gbit/s                      | grq002a-rt11                                           | Northwind Labs, NWL          | Groningen |
| gen-680              | BFU L2VPN EHV001A-GRQ001A-UTR002A 10 Gbit/s    | ehv001a-rt02, utr002a-rt11, grq001a-rt09, utr002a-rt09 | Bluefin University, BFU      | Eindhoven, Utrecht, Groningen |
| gen-683              | BFH LP GOR001A-RTD002A 10 Gbit/s               | rtd002a-rt09, gor001a-rt05                             | Bluefin Hospital, BFH        | Rotterdam, Gorinchem |
| gen-684              | BFU IP GOR002A 10 Gbit/s                       | gor002a-rt08                                           | Bluefin University, BFU      | Gorinchem |
| gen-685              | GFO LP ARN001A-GOR002A 1 Gbit/s                | arn001a-rt02, gor002a-rt03                             | Greenfield Observatory, GFO  | Arnhem, Gorinchem |
| gen-686              | BFU SP UNTAGGED ASV002A 1 Gbit/s               | asv002a-rt09                                           | Bluefin University, BFU      | Amstelveen |
| gen-688              | SLM SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt10                                           | Silverline Museum, SLM       | Gorinchem |
| gen-689              | BFU L2VPN ARN002A-RTD001A-UTR001A 1 Gbit/s     | arn002a-rt07, rtd001a-rt03, rtd001a-rt02, utr001a-rt11 | Bluefin University, BFU      | Arnhem, Rotterdam, Utrecht |
| gen-690              | SLA SP TAGGED GRQ001A 100 Gbit/s               | grq001a-rt02                                           | Silverline Archives, SLA     | Groningen |
| gen-692              | SLM LP ARN002A-ASV001A 1 Gbit/s                | asv001a-rt08, arn002a-rt06                             | Silverline Museum, SLM       | Amstelveen, Arnhem |
| gen-694              | RWI IP AMS002A 10 Gbit/s                       | ams002a-rt09                                           | Redwood Institute, RWI       | Amsterdam |
| gen-695              | NWR LP ARN001A-ARN002A 100 Gbit/s              | arn002a-rt05, arn001a-rt06                             | Northwind Research, NWR      | Arnhem |
| gen-697              | BFU LP ALM001A-GRQ002A 1 Gbit/s                | grq002a-rt06, alm001a-rt09                             | Bluefin University, BFU      | Groningen, Almere |
| gen-698              | GFO L2VPN ARN001A-UTR001A 10 Gbit/s            | arn001a-rt04, utr001a-rt04                             | Greenfield Observatory, GFO  | Arnhem, Utrecht |
| gen-699              | NWL LP EHV002A-GRQ001A 100 Gbit/s              | ehv002a-rt10, grq001a-rt06                             | Northwind Labs, NWL          | Eindhoven, Groningen |
| gen-700              | NWL IP GRQ002A 10 Gbit/s                       | grq002a-rt10                                           | Northwind Labs, NWL          | Groningen |
| gen-701              | NWR L2VPN ALM002A-ARN002A-ENS001A 1 Gbit/s     | alm002a-rt06, arn002a-rt08, ens001a-rt05               | Northwind Research, NWR      | Almere, Arnhem, Enschede |
| gen-704              | SLM SP TAGGED MST002A 100 Gbit/s               | mst002a-rt04                                           | Silverline Museum, SLM       | Maastricht |
| gen-705              | GFC LP ALM002A-MST002A 100 Gbit/s              | alm002a-rt09, mst002a-rt04                             | Greenfield College, GFC      | Almere, Maastricht |
| gen-706              | NWR IP ARN001A 100 Gbit/s                      | arn001a-rt11                                           | Northwind Research, NWR      | Arnhem |
| gen-707              | NWR SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt11                                           | Northwind Research, NWR      | Enschede |
| gen-708              | BFH LP GRQ001A-RTD002A 1 Gbit/s                | grq001a-rt09, rtd002a-rt10                             | Bluefin Hospital, BFH        | Groningen, Rotterdam |
| gen-709              | BFU SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt02                                           | Bluefin University, BFU      | Eindhoven |
| gen-711              | BFH LP MST002A-UTR001A 1 Gbit/s                | utr001a-rt10, mst002a-rt01                             | Bluefin Hospital, BFH        | Utrecht, Maastricht |
| gen-712              | BFU L2VPN ALM001A-GOR002A-MST001A 100 Gbit/s   | gor002a-rt10, alm001a-rt07, mst002a-rt03, mst001a-rt04 | Bluefin University, BFU      | Gorinchem, Almere, Maastricht |
| gen-713              | RWI L2VPN AMS001A-ARN001A-ENS001A 100 Gbit/s   | arn001a-rt11, utr002a-rt01, ens001a-rt02, ams001a-rt05 | Redwood Institute, RWI       | Arnhem, Utrecht, Enschede, Amsterdam |
| gen-714              | GFC L2VPN ALM002A-ARN001A-RTD001A 100 Gbit/s   | rtd001a-rt04, alm002a-rt11, arn001a-rt12               | Greenfield College, GFC      | Rotterdam, Almere, Arnhem |
| gen-716              | RWL IP MST002A 100 Gbit/s                      | mst002a-rt10                                           | Redwood Libraries, RWL       | Maastricht |
| gen-717              | RWL IP GRQ001A 10 Gbit/s                       | grq001a-rt07                                           | Redwood Libraries, RWL       | Groningen |
| gen-719              | SLM LP ARN001A-ARN001A 100 Gbit/s              | arn001a-rt12, arn001a-rt02                             | Silverline Museum, SLM       | Arnhem |
| gen-720              | GFC L2VPN ENS001A-UTR001A-UTR002A 10 Gbit/s    | utr002a-rt04, ens001a-rt02, utr001a-rt12               | Greenfield College, GFC      | Utrecht, Enschede |
| gen-721              | GFO SP UNTAGGED RMD001A 10 Gbit/s              | rmd001a-rt04                                           | Greenfield Observatory, GFO  | Roermond |
| gen-723              | SLM SP TAGGED GOR002A 100 Gbit/s               | gor002a-rt04                                           | Silverline Museum, SLM       | Gorinchem |
| gen-726              | RWL LP GRQ002A-RTD002A 10 Gbit/s               | grq002a-rt05, rtd002a-rt07                             | Redwood Libraries, RWL       | Groningen, Rotterdam |
| gen-728              | BFU IP GOR001A 100 Gbit/s                      | gor001a-rt08                                           | Bluefin University, BFU      | Gorinchem |
| gen-729              | BFH L2VPN MST001A-RTD001A 10 Gbit/s            | rtd001a-rt02, mst001a-rt03, mst001a-rt07               | Bluefin Hospital, BFH        | Rotterdam, Maastricht |
| gen-732              | GFC L2VPN ENS002A-GOR002A 100 Gbit/s           | gor002a-rt08, ens002a-rt01                             | Greenfield College, GFC      | Gorinchem, Enschede |
| gen-733              | SLM SP TAGGED GOR001A 10 Gbit/s                | gor001a-rt06                                           | Silverline Museum, SLM       | Gorinchem |
| gen-734              | RWL LP ALM001A-ENS001A 1 Gbit/s                | ens001a-rt09, alm001a-rt02                             | Redwood Libraries, RWL       | Enschede, Almere |
| gen-735              | RWI L2VPN ALM002A-UTR002A 10 Gbit/s            | utr002a-rt02, alm002a-rt01                             | Redwood Institute, RWI       | Utrecht, Almere |
| gen-737              | BFH LP ALM001A-GOR001A 100 Gbit/s              | gor001a-rt08, alm001a-rt05                             | Bluefin Hospital, BFH        | Gorinchem, Almere |
| gen-738              | BFU L2VPN ASV002A-EHV002A-GRQ002A 1 Gbit/s     | grq002a-rt01, ehv002a-rt07, asv002a-rt04               | Bluefin University, BFU      | Groningen, Eindhoven, Amstelveen |
| gen-739              | GFO L2VPN ALM001A-UTR001A 1 Gbit/s             | alm001a-rt04, utr001a-rt03                             | Greenfield Observatory, GFO  | Almere, Utrecht |
| gen-740              | BFU L2VPN EHV001A-ENS002A-GOR001A 10 Gbit/s    | gor001a-rt05, ens002a-rt04, mst001a-rt02, ehv001a-rt12 | Bluefin University, BFU      | Gorinchem, Enschede, Maastricht, Eindhoven |
| gen-741              | GFO L2VPN ARN002A-RMD001A-UTR001A 100 Gbit/s   | arn002a-rt02, rmd001a-rt06, utr001a-rt05               | Greenfield Observatory, GFO  | Arnhem, Roermond, Utrecht |
| gen-742              | RWL SP UNTAGGED ENS002A 100 Gbit/s             | ens002a-rt05                                           | Redwood Libraries, RWL       | Enschede |
| gen-743              | NWR LP ARN001A-EHV002A 10 Gbit/s               | arn001a-rt10, ehv002a-rt07                             | Northwind Research, NWR      | Arnhem, Eindhoven |
| gen-745              | BFH SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt02                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-749              | GFC SP TAGGED UTR001A 100 Gbit/s               | utr001a-rt09                                           | Greenfield College, GFC      | Utrecht |
| gen-750              | NWR L2VPN ALM002A-ARN001A 10 Gbit/s            | alm002a-rt06, arn001a-rt01                             | Northwind Research, NWR      | Almere, Arnhem |
| gen-751              | SLM SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt04                                           | Silverline Museum, SLM       | Amstelveen |
| gen-752              | RWL L2VPN ENS001A-GOR002A 10 Gbit/s            | ens001a-rt02, gor002a-rt12, gor002a-rt04               | Redwood Libraries, RWL       | Enschede, Gorinchem |
| gen-754              | GFC L2VPN ASV002A-GOR001A 1 Gbit/s             | gor001a-rt06, asv002a-rt12                             | Greenfield College, GFC      | Gorinchem, Amstelveen |
| gen-757              | BFU SP UNTAGGED ASV002A 1 Gbit/s               | asv002a-rt08                                           | Bluefin University, BFU      | Amstelveen |
| gen-761              | BFH L2VPN ARN001A-GOR002A 100 Gbit/s           | gor002a-rt01, arn001a-rt06                             | Bluefin Hospital, BFH        | Gorinchem, Arnhem |
| gen-763              | BFU IP ENS001A 1 Gbit/s                        | ens001a-rt12                                           | Bluefin University, BFU      | Enschede |
| gen-764              | BFU SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt07                                           | Bluefin University, BFU      | Rotterdam |
| gen-765              | GFC LP RTD001A-RTD002A 100 Gbit/s              | rtd002a-rt01, rtd001a-rt08                             | Greenfield College, GFC      | Rotterdam |
| gen-766              | GFC IP AMS002A 10 Gbit/s                       | ams002a-rt02                                           | Greenfield College, GFC      | Amsterdam |
| gen-768              | BFH L2VPN ALM002A-EHV002A 100 Gbit/s           | alm002a-rt10, ehv002a-rt07                             | Bluefin Hospital, BFH        | Almere, Eindhoven |
| gen-769              | RWI LP AMS002A-RMD001A 10 Gbit/s               | ams002a-rt09, rmd001a-rt12                             | Redwood Institute, RWI       | Amsterdam, Roermond |
| gen-771              | RWI L2VPN RMD001A 10 Gbit/s                    | rmd001a-rt09, rmd001a-rt04                             | Redwood Institute, RWI       | Roermond |
| gen-773              | RWL L2VPN ALM001A-GRQ002A-RTD001A 10 Gbit/s    | alm001a-rt05, grq002a-rt07, rtd001a-rt04               | Redwood Libraries, RWL       | Almere, Groningen, Rotterdam |
| gen-776              | RWL IP RMD002A 1 Gbit/s                        | rmd002a-rt11                                           | Redwood Libraries, RWL       | Roermond |
| gen-777              | BFH LP RMD001A-UTR001A 100 Gbit/s              | utr001a-rt06, rmd001a-rt07                             | Bluefin Hospital, BFH        | Utrecht, Roermond |
| gen-778              | GFC SP TAGGED AMS001A 100 Gbit/s               | ams001a-rt09                                           | Greenfield College, GFC      | Amsterdam |
| gen-779              | GFO LP ARN001A-UTR002A 100 Gbit/s              | arn001a-rt05, utr002a-rt03                             | Greenfield Observatory, GFO  | Arnhem, Utrecht |
| gen-780              | RWI IP AMS002A 100 Gbit/s                      | ams002a-rt01                                           | Redwood Institute, RWI       | Amsterdam |
| gen-782              | BFH L2VPN ARN001A-RMD001A 100 Gbit/s           | rmd001a-rt07, arn001a-rt12                             | Bluefin Hospital, BFH        | Roermond, Arnhem |
| gen-783              | SLA IP UTR001A 100 Gbit/s                      | utr001a-rt08                                           | Silverline Archives, SLA     | Utrecht |
| gen-784              | NWR SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt01                                           | Northwind Research, NWR      | Arnhem |
| gen-786              | SLA IP AMS002A 1 Gbit/s                        | ams002a-rt12                                           | Silverline Archives, SLA     | Amsterdam |
| gen-787              | GFO IP EHV001A 1 Gbit/s                        | ehv001a-rt08                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-788              | BFU IP GRQ001A 100 Gbit/s                      | grq001a-rt06                                           | Bluefin University, BFU      | Groningen |
| gen-791              | RWL L2VPN EHV002A-GOR001A 10 Gbit/s            | ehv002a-rt08, ehv002a-rt02, gor001a-rt01               | Redwood Libraries, RWL       | Eindhoven, Gorinchem |
| gen-794              | GFC IP ASV002A 10 Gbit/s                       | asv002a-rt01                                           | Greenfield College, GFC      | Amstelveen |
| gen-795              | GFC SP TAGGED RTD002A 100 Gbit/s               | rtd002a-rt03                                           | Greenfield College, GFC      | Rotterdam |
| gen-797              | RWL IP EHV002A 100 Gbit/s                      | ehv002a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-798              | GFC SP UNTAGGED AMS002A 1 Gbit/s               | ams002a-rt03                                           | Greenfield College, GFC      | Amsterdam |
| gen-799              | NWR SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt04                                           | Northwind Research, NWR      | Almere |
| gen-800              | BFH SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt06                                           | Bluefin Hospital, BFH        | Almere |
| gen-802              | SLM SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt01                                           | Silverline Museum, SLM       | Groningen |
| gen-803              | BFH LP EHV001A-EHV002A 1 Gbit/s                | ehv002a-rt06, ehv001a-rt12                             | Bluefin Hospital, BFH        | Eindhoven |
| gen-804              | NWL LP EHV001A-MST002A 100 Gbit/s              | mst002a-rt03, ehv001a-rt12                             | Northwind Labs, NWL          | Maastricht, Eindhoven |
| gen-805              | NWL IP GOR002A 10 Gbit/s                       | gor002a-rt02                                           | Northwind Labs, NWL          | Gorinchem |
| gen-806              | RWI IP AMS001A 1 Gbit/s                        | ams001a-rt08                                           | Redwood Institute, RWI       | Amsterdam |
| gen-808              | GFO IP RMD001A 1 Gbit/s                        | rmd001a-rt12                                           | Greenfield Observatory, GFO  | Roermond |
| gen-809              | RWL SP TAGGED MST001A 1 Gbit/s                 | mst001a-rt10                                           | Redwood Libraries, RWL       | Maastricht |
| gen-810              | GFC IP UTR002A 1 Gbit/s                        | utr002a-rt03                                           | Greenfield College, GFC      | Utrecht |
| gen-815              | NWL IP GOR001A 100 Gbit/s                      | gor001a-rt03                                           | Northwind Labs, NWL          | Gorinchem |
| gen-816              | GFC L2VPN GOR002A-RMD002A 100 Gbit/s           | gor002a-rt03, rmd002a-rt05                             | Greenfield College, GFC      | Gorinchem, Roermond |
| gen-818              | RWL SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt10                                           | Redwood Libraries, RWL       | Enschede |
| gen-819              | BFU IP RTD002A 100 Gbit/s                      | rtd002a-rt07                                           | Bluefin University, BFU      | Rotterdam |
| gen-820              | BFU SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt03                                           | Bluefin University, BFU      | Arnhem |
| gen-822              | RWI LP ENS002A-MST002A 10 Gbit/s               | mst002a-rt07, ens002a-rt07                             | Redwood Institute, RWI       | Maastricht, Enschede |
| gen-823              | GFC IP GOR002A 1 Gbit/s                        | gor002a-rt12                                           | Greenfield College, GFC      | Gorinchem |
| gen-825              | NWR SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt11                                           | Northwind Research, NWR      | Roermond |
| gen-827              | NWL LP ALM002A-EHV002A 100 Gbit/s              | alm002a-rt02, ehv002a-rt08                             | Northwind Labs, NWL          | Almere, Eindhoven |
| gen-828              | GFO LP AMS002A-RTD001A 1 Gbit/s                | rtd001a-rt09, ams002a-rt05                             | Greenfield Observatory, GFO  | Rotterdam, Amsterdam |
| gen-832              | RWL LP MST001A-RTD002A 10 Gbit/s               | rtd002a-rt08, mst001a-rt03                             | Redwood Libraries, RWL       | Rotterdam, Maastricht |
| gen-833              | GFO L2VPN EHV001A-GOR001A-RTD002A 10 Gbit/s    | rtd002a-rt09, gor001a-rt07, ehv001a-rt04               | Greenfield Observatory, GFO  | Rotterdam, Gorinchem, Eindhoven |
| gen-834              | NWL LP ASV001A-EHV002A 10 Gbit/s               | ehv002a-rt08, asv001a-rt02                             | Northwind Labs, NWL          | Eindhoven, Amstelveen |
| gen-835              | BFH LP ALM001A-ARN001A 10 Gbit/s               | alm001a-rt06, arn001a-rt12                             | Bluefin Hospital, BFH        | Almere, Arnhem |
| gen-836              | BFH IP ENS002A 100 Gbit/s                      | ens002a-rt06                                           | Bluefin Hospital, BFH        | Enschede |
| gen-838              | SLA L2VPN ALM002A-ARN001A 100 Gbit/s           | alm002a-rt01, arn001a-rt06                             | Silverline Archives, SLA     | Almere, Arnhem |
| gen-839              | BFH SP TAGGED ASV002A 10 Gbit/s                | asv002a-rt10                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-840              | RWI L2VPN GOR002A-RMD002A-RTD002A 100 Gbit/s   | gor002a-rt11, rmd002a-rt07, gor002a-rt12, rtd002a-rt05 | Redwood Institute, RWI       | Gorinchem, Roermond, Rotterdam |
| gen-844              | RWL L2VPN RTD002A-UTR001A 10 Gbit/s            | utr001a-rt05, rtd002a-rt11, utr001a-rt03               | Redwood Libraries, RWL       | Utrecht, Rotterdam |
| gen-848              | RWI SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt01                                           | Redwood Institute, RWI       | Groningen |
| gen-849              | BFU L2VPN EHV002A-GOR001A-GRQ001A 1 Gbit/s     | ehv002a-rt09, grq001a-rt08, gor001a-rt01               | Bluefin University, BFU      | Eindhoven, Groningen, Gorinchem |
| gen-850              | GFO L2VPN AMS001A-ARN001A 100 Gbit/s           | arn001a-rt09, ams001a-rt09                             | Greenfield Observatory, GFO  | Arnhem, Amsterdam |
| gen-851              | GFO IP RTD002A 10 Gbit/s                       | rtd002a-rt03                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-852              | BFU SP TAGGED GOR001A 10 Gbit/s                | gor001a-rt03                                           | Bluefin University, BFU      | Gorinchem |
| gen-853              | SLM SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt06                                           | Silverline Museum, SLM       | Arnhem |
| gen-854              | BFU SP UNTAGGED RTD001A 100 Gbit/s             | rtd001a-rt04                                           | Bluefin University, BFU      | Rotterdam |
| gen-856              | GFC SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt11                                           | Greenfield College, GFC      | Gorinchem |
| gen-858              | RWL LP RMD001A-UTR001A 100 Gbit/s              | rmd001a-rt10, utr001a-rt01                             | Redwood Libraries, RWL       | Roermond, Utrecht |
| gen-859              | RWL LP MST001A-RTD001A 10 Gbit/s               | mst001a-rt02, rtd001a-rt02                             | Redwood Libraries, RWL       | Maastricht, Rotterdam |
| gen-861              | RWI SP UNTAGGED ALM002A 100 Gbit/s             | alm002a-rt03                                           | Redwood Institute, RWI       | Almere |
| gen-864              | NWR LP ASV002A-GOR001A 1 Gbit/s                | asv002a-rt10, gor001a-rt06                             | Northwind Research, NWR      | Amstelveen, Gorinchem |
| gen-865              | GFO IP RMD002A 100 Gbit/s                      | rmd002a-rt04                                           | Greenfield Observatory, GFO  | Roermond |
| gen-866              | RWI SP TAGGED ENS002A 100 Gbit/s               | ens002a-rt08                                           | Redwood Institute, RWI       | Enschede |
| gen-868              | BFU IP EHV002A 10 Gbit/s                       | ehv002a-rt09                                           | Bluefin University, BFU      | Eindhoven |
| gen-869              | GFO SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt02                                           | Greenfield Observatory, GFO  | Almere |
| gen-870              | NWR IP ENS001A 1 Gbit/s                        | ens001a-rt04                                           | Northwind Research, NWR      | Enschede |
| gen-872              | RWI IP EHV002A 100 Gbit/s                      | ehv002a-rt11                                           | Redwood Institute, RWI       | Eindhoven |
| gen-879              | NWL L2VPN EHV002A-GOR002A-RMD002A 100 Gbit/s   | gor002a-rt04, ehv002a-rt02, rmd002a-rt03               | Northwind Labs, NWL          | Gorinchem, Eindhoven, Roermond |
| gen-881              | RWL SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt01                                           | Redwood Libraries, RWL       | Enschede |
| gen-883              | GFC L2VPN ALM001A-AMS002A 1 Gbit/s             | alm001a-rt01, ams002a-rt03                             | Greenfield College, GFC      | Almere, Amsterdam |
| gen-884              | SLM SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt12                                           | Silverline Museum, SLM       | Maastricht |
| gen-886              | NWL LP ALM001A-RMD001A 100 Gbit/s              | rmd001a-rt04, alm001a-rt07                             | Northwind Labs, NWL          | Roermond, Almere |
| gen-887              | GFC L2VPN ALM001A-ALM002A 100 Gbit/s           | alm001a-rt01, alm002a-rt10                             | Greenfield College, GFC      | Almere |
| gen-888              | GFC IP GRQ001A 10 Gbit/s                       | grq001a-rt02                                           | Greenfield College, GFC      | Groningen |
| gen-889              | GFC IP RMD002A 1 Gbit/s                        | rmd002a-rt09                                           | Greenfield College, GFC      | Roermond |
| gen-890              | NWL LP EHV001A-EHV002A 10 Gbit/s               | ehv002a-rt09, ehv001a-rt08                             | Northwind Labs, NWL          | Eindhoven |
| gen-892              | GFO LP GRQ002A-UTR001A 10 Gbit/s               | grq002a-rt09, utr001a-rt09                             | Greenfield Observatory, GFO  | Groningen, Utrecht |
| gen-893              | SLA L2VPN AMS001A-ARN001A-GOR002A 100 Gbit/s   | ams001a-rt09, gor002a-rt05, arn001a-rt01               | Silverline Archives, SLA     | Amsterdam, Gorinchem, Arnhem |
| gen-895              | BFH IP UTR002A 1 Gbit/s                        | utr002a-rt12                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-897              | GFO L2VPN ARN001A-ARN002A-RMD001A 10 Gbit/s    | arn001a-rt11, rmd001a-rt12, arn001a-rt08, arn002a-rt09 | Greenfield Observatory, GFO  | Arnhem, Roermond |
| gen-901              | GFO IP AMS002A 10 Gbit/s                       | ams002a-rt10                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-902              | GFC L2VPN ARN001A-ASV002A-EHV002A 100 Gbit/s   | asv002a-rt04, arn001a-rt11, ehv002a-rt08               | Greenfield College, GFC      | Amstelveen, Arnhem, Eindhoven |
| gen-903              | GFO L2VPN ARN002A-ENS001A-MST001A 100 Gbit/s   | mst001a-rt01, ens001a-rt02, arn002a-rt12               | Greenfield Observatory, GFO  | Maastricht, Enschede, Arnhem |
| gen-904              | NWL IP ASV001A 100 Gbit/s                      | asv001a-rt04                                           | Northwind Labs, NWL          | Amstelveen |
| gen-905              | SLM L2VPN AMS001A-ARN001A-GOR002A 100 Gbit/s   | ams001a-rt05, gor002a-rt09, arn001a-rt09, grq001a-rt03 | Silverline Museum, SLM       | Amsterdam, Gorinchem, Arnhem, Groningen |
| gen-908              | SLA SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt01                                           | Silverline Archives, SLA     | Arnhem |
| gen-909              | SLA L2VPN ARN002A-ASV002A 1 Gbit/s             | arn002a-rt08, asv002a-rt01                             | Silverline Archives, SLA     | Arnhem, Amstelveen |
| gen-910              | GFO SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt02                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-911              | NWR LP ARN002A-ASV002A 1 Gbit/s                | arn002a-rt11, asv002a-rt03                             | Northwind Research, NWR      | Arnhem, Amstelveen |
| gen-912              | SLM IP ARN001A 100 Gbit/s                      | arn001a-rt02                                           | Silverline Museum, SLM       | Arnhem |
| gen-913              | GFO IP RTD002A 1 Gbit/s                        | rtd002a-rt08                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-914              | SLM L2VPN ALM002A-ARN001A 10 Gbit/s            | alm002a-rt10, arn001a-rt07                             | Silverline Museum, SLM       | Almere, Arnhem |
| gen-918              | BFU IP ARN002A 1 Gbit/s                        | arn002a-rt05                                           | Bluefin University, BFU      | Arnhem |
| gen-919              | GFO LP GOR002A-GRQ002A 1 Gbit/s                | grq002a-rt05, gor002a-rt11                             | Greenfield Observatory, GFO  | Groningen, Gorinchem |
| gen-921              | RWL IP ARN002A 1 Gbit/s                        | arn002a-rt05                                           | Redwood Libraries, RWL       | Arnhem |
| gen-922              | BFH L2VPN ARN001A-RMD002A-UTR002A 1 Gbit/s     | utr002a-rt09, rmd002a-rt07, arn001a-rt04               | Bluefin Hospital, BFH        | Utrecht, Roermond, Arnhem |
| gen-923              | SLM L2VPN ASV002A-GOR001A 100 Gbit/s           | gor001a-rt10, asv002a-rt07                             | Silverline Museum, SLM       | Gorinchem, Amstelveen |
| gen-927              | BFH L2VPN ALM002A-MST001A 1 Gbit/s             | alm002a-rt12, mst001a-rt12, mst001a-rt03               | Bluefin Hospital, BFH        | Almere, Maastricht |
| gen-929              | NWR L2VPN ALM001A-ASV002A 10 Gbit/s            | asv002a-rt11, alm001a-rt09                             | Northwind Research, NWR      | Amstelveen, Almere |
| gen-930              | SLA IP UTR002A 1 Gbit/s                        | utr002a-rt01                                           | Silverline Archives, SLA     | Utrecht |
| gen-932              | BFU SP UNTAGGED EHV002A 1 Gbit/s               | ehv002a-rt10                                           | Bluefin University, BFU      | Eindhoven |
| gen-933              | RWL LP ARN001A-RMD002A 10 Gbit/s               | arn001a-rt04, rmd002a-rt05                             | Redwood Libraries, RWL       | Arnhem, Roermond |
| gen-934              | RWL SP UNTAGGED RMD002A 1 Gbit/s               | rmd002a-rt03                                           | Redwood Libraries, RWL       | Roermond |
| gen-936              | BFU L2VPN ENS002A-GRQ001A-MST002A 1 Gbit/s     | utr001a-rt04, grq001a-rt12, ens002a-rt11, mst002a-rt09 | Bluefin University, BFU      | Utrecht, Groningen, Enschede, Maastricht |
| gen-939              | BFU SP TAGGED GOR002A 1 Gbit/s                 | gor002a-rt03                                           | Bluefin University, BFU      | Gorinchem |
| gen-940              | NWL SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt12                                           | Northwind Labs, NWL          | Almere |
| gen-941              | GFO LP AMS002A-ENS002A 100 Gbit/s              | ams002a-rt12, ens002a-rt07                             | Greenfield Observatory, GFO  | Amsterdam, Enschede |
| gen-942              | NWL L2VPN ALM001A-ARN001A-EHV002A 1 Gbit/s     | arn001a-rt10, alm001a-rt06, ehv002a-rt06               | Northwind Labs, NWL          | Arnhem, Almere, Eindhoven |
| gen-944              | NWL L2VPN GRQ002A-RMD002A 10 Gbit/s            | rmd002a-rt09, grq002a-rt01                             | Northwind Labs, NWL          | Roermond, Groningen |
| gen-947              | SLA IP UTR002A 1 Gbit/s                        | utr002a-rt10                                           | Silverline Archives, SLA     | Utrecht |
| gen-948              | NWR LP ALM001A-GRQ002A 1 Gbit/s                | alm001a-rt04, grq002a-rt09                             | Northwind Research, NWR      | Almere, Groningen |
| gen-949              | NWR IP GOR002A 1 Gbit/s                        | gor002a-rt03                                           | Northwind Research, NWR      | Gorinchem |
| gen-950              | GFC IP EHV002A 10 Gbit/s                       | ehv002a-rt01                                           | Greenfield College, GFC      | Eindhoven |
| gen-951              | RWI IP RTD001A 100 Gbit/s                      | rtd001a-rt11                                           | Redwood Institute, RWI       | Rotterdam |
| gen-953              | GFO LP ALM002A-MST002A 10 Gbit/s               | alm002a-rt06, mst002a-rt04                             | Greenfield Observatory, GFO  | Almere, Maastricht |
| gen-956              | BFH SP UNTAGGED ASV002A 1 Gbit/s               | asv002a-rt10                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-957              | GFC L2VPN AMS001A-ENS002A-GOR001A 1 Gbit/s     | gor002a-rt05, gor001a-rt10, ams001a-rt06, ens002a-rt05 | Greenfield College, GFC      | Gorinchem, Amsterdam, Enschede |
| gen-958              | BFU IP ALM001A 10 Gbit/s                       | alm001a-rt11                                           | Bluefin University, BFU      | Almere |
| gen-959              | BFH L2VPN ALM001A-EHV001A-GRQ001A 10 Gbit/s    | ehv001a-rt01, grq001a-rt09, alm001a-rt09               | Bluefin Hospital, BFH        | Eindhoven, Groningen, Almere |
| gen-963              | RWI SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt04                                           | Redwood Institute, RWI       | Arnhem |
| gen-964              | GFC SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt07                                           | Greenfield College, GFC      | Almere |
| gen-968              | SLM LP AMS002A-GRQ001A 1 Gbit/s                | ams002a-rt08, grq001a-rt09                             | Silverline Museum, SLM       | Amsterdam, Groningen |
| gen-969              | GFC L2VPN GOR002A-MST002A 100 Gbit/s           | mst002a-rt09, gor002a-rt02                             | Greenfield College, GFC      | Maastricht, Gorinchem |
| gen-970              | GFC LP ALM002A-RTD002A 100 Gbit/s              | alm002a-rt10, rtd002a-rt07                             | Greenfield College, GFC      | Almere, Rotterdam |
| gen-971              | BFU LP MST001A-MST001A 1 Gbit/s                | mst001a-rt02, mst001a-rt09                             | Bluefin University, BFU      | Maastricht |
| gen-976              | GFO SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt11                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-980              | GFC L2VPN RTD001A-UTR001A 1 Gbit/s             | rtd001a-rt12, rtd001a-rt06, utr001a-rt07               | Greenfield College, GFC      | Rotterdam, Utrecht |
| gen-982              | RWI L2VPN ALM002A-EHV001A-GRQ001A 1 Gbit/s     | rtd001a-rt09, alm002a-rt09, grq001a-rt02, ehv001a-rt06 | Redwood Institute, RWI       | Rotterdam, Almere, Groningen, Eindhoven |
| gen-984              | RWL LP ALM002A-ALM002A 100 Gbit/s              | alm002a-rt02, alm002a-rt05                             | Redwood Libraries, RWL       | Almere |
| gen-986              | RWI SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt07                                           | Redwood Institute, RWI       | Eindhoven |
| gen-987              | GFO SP TAGGED RMD002A 100 Gbit/s               | rmd002a-rt07                                           | Greenfield Observatory, GFO  | Roermond |
| gen-988              | GFC LP ENS002A-MST001A 10 Gbit/s               | mst001a-rt11, ens002a-rt09                             | Greenfield College, GFC      | Maastricht, Enschede |
| gen-989              | RWI SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt03                                           | Redwood Institute, RWI       | Arnhem |
| gen-990              | RWL SP TAGGED GOR001A 1 Gbit/s                 | gor001a-rt02                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-991              | BFH SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt06                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-992              | GFC LP RTD001A-RTD002A 100 Gbit/s              | rtd002a-rt05, rtd001a-rt05                             | Greenfield College, GFC      | Rotterdam |
| gen-994              | SLA SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt12                                           | Silverline Archives, SLA     | Almere |
| gen-996              | BFU IP EHV001A 100 Gbit/s                      | ehv001a-rt12                                           | Bluefin University, BFU      | Eindhoven |
| gen-997              | BFU L2VPN GOR002A-RMD001A 10 Gbit/s            | rmd001a-rt02, gor002a-rt02                             | Bluefin University, BFU      | Roermond, Gorinchem |
| gen-998              | GFC L2VPN ALM002A-ARN002A-ENS002A 10 Gbit/s    | ens002a-rt07, arn002a-rt01, rtd001a-rt05, alm002a-rt04 | Greenfield College, GFC      | Enschede, Arnhem, Rotterdam, Almere |
| gen-999              | RWI IP EHV002A 10 Gbit/s                       | ehv002a-rt06                                           | Redwood Institute, RWI       | Eindhoven |
| gen-1000             | BFU SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt03                                           | Bluefin University, BFU      | Arnhem |
| gen-1001             | BFH IP GOR001A 100 Gbit/s                      | gor001a-rt12                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-1002             | GFC SP UNTAGGED RTD002A 10 Gbit/s              | rtd002a-rt01                                           | Greenfield College, GFC      | Rotterdam |
| gen-1003             | GFC LP GOR002A-GRQ002A 10 Gbit/s               | grq002a-rt09, gor002a-rt07                             | Greenfield College, GFC      | Groningen, Gorinchem |
| gen-1005             | BFU LP ARN002A-RTD001A 100 Gbit/s              | arn002a-rt05, rtd001a-rt12                             | Bluefin University, BFU      | Arnhem, Rotterdam |
| gen-1006             | GFC L2VPN AMS001A-GRQ001A-UTR001A 10 Gbit/s    | grq001a-rt10, utr001a-rt05, ams001a-rt08               | Greenfield College, GFC      | Groningen, Utrecht, Amsterdam |
| gen-1008             | RWL SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt08                                           | Redwood Libraries, RWL       | Maastricht |
| gen-1009             | RWI SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt11                                           | Redwood Institute, RWI       | Groningen |
| gen-1011             | RWL IP ENS001A 100 Gbit/s                      | ens001a-rt05                                           | Redwood Libraries, RWL       | Enschede |
| gen-1012             | GFO LP ASV001A-GRQ002A 100 Gbit/s              | asv001a-rt04, grq002a-rt08                             | Greenfield Observatory, GFO  | Amstelveen, Groningen |
| gen-1013             | GFO SP UNTAGGED ASV002A 10 Gbit/s              | asv002a-rt07                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-1014             | NWL SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt09                                           | Northwind Labs, NWL          | Maastricht |
| gen-1019             | NWL SP TAGGED MST001A 10 Gbit/s                | mst001a-rt10                                           | Northwind Labs, NWL          | Maastricht |
| gen-1020             | BFU L2VPN RMD001A-UTR001A 1 Gbit/s             | utr001a-rt11, rmd001a-rt11                             | Bluefin University, BFU      | Utrecht, Roermond |
| gen-1021             | GFO IP GOR002A 1 Gbit/s                        | gor002a-rt10                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-1023             | NWR IP GRQ001A 100 Gbit/s                      | grq001a-rt05                                           | Northwind Research, NWR      | Groningen |
| gen-1025             | GFC IP MST001A 1 Gbit/s                        | mst001a-rt08                                           | Greenfield College, GFC      | Maastricht |
| gen-1027             | NWR IP ASV001A 100 Gbit/s                      | asv001a-rt12                                           | Northwind Research, NWR      | Amstelveen |
| gen-1028             | SLM IP MST002A 10 Gbit/s                       | mst002a-rt03                                           | Silverline Museum, SLM       | Maastricht |
| gen-1029             | GFO IP ARN002A 1 Gbit/s                        | arn002a-rt02                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-1030             | GFO SP UNTAGGED ENS001A 10 Gbit/s              | ens001a-rt12                                           | Greenfield Observatory, GFO  | Enschede |
| gen-1033             | SLM IP MST002A 100 Gbit/s                      | mst002a-rt10                                           | Silverline Museum, SLM       | Maastricht |
| gen-1034             | RWL LP EHV001A-RTD001A 10 Gbit/s               | ehv001a-rt06, rtd001a-rt10                             | Redwood Libraries, RWL       | Eindhoven, Rotterdam |
| gen-1035             | BFH SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt10                                           | Bluefin Hospital, BFH        | Almere |
| gen-1038             | RWL LP EHV002A-RTD002A 1 Gbit/s                | rtd002a-rt06, ehv002a-rt01                             | Redwood Libraries, RWL       | Rotterdam, Eindhoven |
| gen-1039             | SLA LP ASV001A-MST002A 10 Gbit/s               | mst002a-rt11, asv001a-rt10                             | Silverline Archives, SLA     | Maastricht, Amstelveen |
| gen-1040             | NWR IP MST001A 1 Gbit/s                        | mst001a-rt01                                           | Northwind Research, NWR      | Maastricht |
| gen-1041             | NWL LP ALM002A-ASV001A 100 Gbit/s              | alm002a-rt09, asv001a-rt02                             | Northwind Labs, NWL          | Almere, Amstelveen |
| gen-1043             | GFC SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt02                                           | Greenfield College, GFC      | Arnhem |
| gen-1044             | GFC IP ASV001A 10 Gbit/s                       | asv001a-rt02                                           | Greenfield College, GFC      | Amstelveen |
| gen-1045             | GFC L2VPN ALM001A-EHV001A-GOR002A 100 Gbit/s   | gor002a-rt09, ehv001a-rt07, rtd002a-rt08, alm001a-rt07 | Greenfield College, GFC      | Gorinchem, Eindhoven, Rotterdam, Almere |
| gen-1046             | RWI L2VPN ENS002A-GRQ001A-MST002A 10 Gbit/s    | mst002a-rt10, grq001a-rt04, ens002a-rt08               | Redwood Institute, RWI       | Maastricht, Groningen, Enschede |
| gen-1048             | RWL LP ENS002A-RTD002A 1 Gbit/s                | rtd002a-rt05, ens002a-rt11                             | Redwood Libraries, RWL       | Rotterdam, Enschede |
| gen-1049             | SLA LP ARN002A-GRQ001A 10 Gbit/s               | arn002a-rt04, grq001a-rt12                             | Silverline Archives, SLA     | Arnhem, Groningen |
| gen-1050             | NWL IP MST001A 1 Gbit/s                        | mst001a-rt06                                           | Northwind Labs, NWL          | Maastricht |
| gen-1053             | RWI LP AMS001A-ARN002A 10 Gbit/s               | ams001a-rt09, arn002a-rt12                             | Redwood Institute, RWI       | Amsterdam, Arnhem |
| gen-1054             | SLM SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt04                                           | Silverline Museum, SLM       | Groningen |
| gen-1056             | BFU L2VPN ENS001A-GOR001A-GRQ002A 1 Gbit/s     | gor001a-rt10, ens001a-rt02, grq002a-rt01               | Bluefin University, BFU      | Gorinchem, Enschede, Groningen |
| gen-1057             | BFU SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt10                                           | Bluefin University, BFU      | Arnhem |
| gen-1062             | SLM SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt06                                           | Silverline Museum, SLM       | Arnhem |
| gen-1066             | BFU IP UTR001A 10 Gbit/s                       | utr001a-rt06                                           | Bluefin University, BFU      | Utrecht |
| gen-1067             | GFC LP ENS001A-UTR001A 10 Gbit/s               | ens001a-rt01, utr001a-rt11                             | Greenfield College, GFC      | Enschede, Utrecht |
| gen-1068             | RWI LP ALM001A-UTR002A 100 Gbit/s              | alm001a-rt08, utr002a-rt05                             | Redwood Institute, RWI       | Almere, Utrecht |
| gen-1069             | BFH SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt06                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1070             | BFU IP ALM002A 1 Gbit/s                        | alm002a-rt09                                           | Bluefin University, BFU      | Almere |
| gen-1071             | GFC L2VPN GRQ001A-RMD001A 1 Gbit/s             | rmd001a-rt10, grq001a-rt08                             | Greenfield College, GFC      | Roermond, Groningen |
| gen-1072             | BFH SP UNTAGGED ALM002A 100 Gbit/s             | alm002a-rt05                                           | Bluefin Hospital, BFH        | Almere |
| gen-1074             | GFO IP RTD002A 1 Gbit/s                        | rtd002a-rt07                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1076             | GFO SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt01                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1077             | GFO SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt01                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1078             | RWI LP GRQ002A-RTD001A 10 Gbit/s               | grq002a-rt07, rtd001a-rt12                             | Redwood Institute, RWI       | Groningen, Rotterdam |
| gen-1079             | RWI L2VPN RMD001A-RTD002A 10 Gbit/s            | rmd001a-rt03, rtd002a-rt11                             | Redwood Institute, RWI       | Roermond, Rotterdam |
| gen-1080             | SLM IP ALM001A 100 Gbit/s                      | alm001a-rt12                                           | Silverline Museum, SLM       | Almere |
| gen-1082             | RWI LP AMS002A-UTR001A 100 Gbit/s              | utr001a-rt06, ams002a-rt09                             | Redwood Institute, RWI       | Utrecht, Amsterdam |
| gen-1083             | NWL IP RMD002A 100 Gbit/s                      | rmd002a-rt09                                           | Northwind Labs, NWL          | Roermond |
| gen-1084             | NWL SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt06                                           | Northwind Labs, NWL          | Groningen |
| gen-1086             | RWI LP ALM001A-AMS002A 10 Gbit/s               | alm001a-rt10, ams002a-rt06                             | Redwood Institute, RWI       | Almere, Amsterdam |
| gen-1088             | RWI IP UTR001A 10 Gbit/s                       | utr001a-rt12                                           | Redwood Institute, RWI       | Utrecht |
| gen-1089             | SLM SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt07                                           | Silverline Museum, SLM       | Arnhem |
| gen-1090             | GFC SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt07                                           | Greenfield College, GFC      | Arnhem |
| gen-1091             | SLA LP GOR001A-GOR002A 1 Gbit/s                | gor002a-rt06, gor001a-rt07                             | Silverline Archives, SLA     | Gorinchem |
| gen-1092             | BFH L2VPN GRQ002A-RMD001A-RTD002A 100 Gbit/s   | rmd001a-rt09, grq002a-rt01, rtd002a-rt05               | Bluefin Hospital, BFH        | Roermond, Groningen, Rotterdam |
| gen-1094             | BFU IP ALM002A 10 Gbit/s                       | alm002a-rt06                                           | Bluefin University, BFU      | Almere |
| gen-1095             | BFU SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt06                                           | Bluefin University, BFU      | Arnhem |
| gen-1096             | BFH IP GOR001A 10 Gbit/s                       | gor001a-rt06                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-1098             | BFU SP TAGGED ASV002A 100 Gbit/s               | asv002a-rt04                                           | Bluefin University, BFU      | Amstelveen |
| gen-1099             | RWI LP ENS001A-ENS002A 10 Gbit/s               | ens001a-rt12, ens002a-rt03                             | Redwood Institute, RWI       | Enschede |
| gen-1100             | SLA L2VPN ARN002A-GRQ002A-UTR002A 10 Gbit/s    | arn002a-rt04, utr002a-rt02, grq002a-rt04               | Silverline Archives, SLA     | Arnhem, Utrecht, Groningen |
| gen-1101             | GFC LP AMS002A-ARN002A 10 Gbit/s               | ams002a-rt02, arn002a-rt07                             | Greenfield College, GFC      | Amsterdam, Arnhem |
| gen-1102             | RWI SP UNTAGGED RTD001A 100 Gbit/s             | rtd001a-rt04                                           | Redwood Institute, RWI       | Rotterdam |
| gen-1103             | BFH SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt11                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1105             | SLM L2VPN AMS001A-GRQ001A 10 Gbit/s            | ams001a-rt02, grq001a-rt08                             | Silverline Museum, SLM       | Amsterdam, Groningen |
| gen-1107             | NWL SP TAGGED GRQ001A 100 Gbit/s               | grq001a-rt04                                           | Northwind Labs, NWL          | Groningen |
| gen-1109             | GFC IP RTD002A 1 Gbit/s                        | rtd002a-rt06                                           | Greenfield College, GFC      | Rotterdam |
| gen-1110             | BFH SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt04                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1111             | RWI L2VPN ENS002A-UTR001A 10 Gbit/s            | ens002a-rt06, utr001a-rt01                             | Redwood Institute, RWI       | Enschede, Utrecht |
| gen-1114             | GFO SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt07                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-1116             | RWL L2VPN ENS002A-GRQ001A-MST002A 10 Gbit/s    | utr001a-rt01, mst002a-rt01, grq001a-rt11, ens002a-rt11 | Redwood Libraries, RWL       | Utrecht, Maastricht, Groningen, Enschede |
| gen-1117             | SLM IP MST002A 10 Gbit/s                       | mst002a-rt04                                           | Silverline Museum, SLM       | Maastricht |
| gen-1118             | SLM IP ASV002A 1 Gbit/s                        | asv002a-rt09                                           | Silverline Museum, SLM       | Amstelveen |
| gen-1119             | NWR LP MST001A-RMD002A 100 Gbit/s              | mst001a-rt09, rmd002a-rt02                             | Northwind Research, NWR      | Maastricht, Roermond |
| gen-1120             | RWL IP MST002A 1 Gbit/s                        | mst002a-rt11                                           | Redwood Libraries, RWL       | Maastricht |
| gen-1121             | GFO IP AMS002A 10 Gbit/s                       | ams002a-rt06                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1123             | GFC IP GRQ002A 10 Gbit/s                       | grq002a-rt01                                           | Greenfield College, GFC      | Groningen |
| gen-1124             | NWL IP ALM001A 100 Gbit/s                      | alm001a-rt12                                           | Northwind Labs, NWL          | Almere |
| gen-1125             | GFC L2VPN ARN002A-MST002A 100 Gbit/s           | mst002a-rt03, arn002a-rt10                             | Greenfield College, GFC      | Maastricht, Arnhem |
| gen-1126             | BFH LP ALM001A-ALM001A 10 Gbit/s               | alm001a-rt04, alm001a-rt11                             | Bluefin Hospital, BFH        | Almere |
| gen-1127             | NWR SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt07                                           | Northwind Research, NWR      | Almere |
| gen-1129             | NWL IP ALM001A 1 Gbit/s                        | alm001a-rt03                                           | Northwind Labs, NWL          | Almere |
| gen-1130             | SLM SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt09                                           | Silverline Museum, SLM       | Almere |
| gen-1131             | SLA LP AMS001A-GRQ002A 10 Gbit/s               | grq002a-rt10, ams001a-rt03                             | Silverline Archives, SLA     | Groningen, Amsterdam |
| gen-1132             | RWI SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt05                                           | Redwood Institute, RWI       | Arnhem |
| gen-1133             | RWI IP GOR001A 10 Gbit/s                       | gor001a-rt11                                           | Redwood Institute, RWI       | Gorinchem |
| gen-1135             | RWL L2VPN EHV002A-UTR002A 10 Gbit/s            | ehv002a-rt10, utr002a-rt10                             | Redwood Libraries, RWL       | Eindhoven, Utrecht |
| gen-1136             | GFO IP AMS001A 1 Gbit/s                        | ams001a-rt06                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1137             | SLA L2VPN GOR001A-GRQ001A 10 Gbit/s            | grq001a-rt11, gor001a-rt10                             | Silverline Archives, SLA     | Groningen, Gorinchem |
| gen-1138             | GFO LP ENS002A-RMD001A 1 Gbit/s                | rmd001a-rt02, ens002a-rt07                             | Greenfield Observatory, GFO  | Roermond, Enschede |
| gen-1139             | RWI SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt06                                           | Redwood Institute, RWI       | Arnhem |
| gen-1140             | RWL L2VPN ALM002A-ENS001A 100 Gbit/s           | ens001a-rt09, alm002a-rt09                             | Redwood Libraries, RWL       | Enschede, Almere |
| gen-1141             | GFC SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt09                                           | Greenfield College, GFC      | Roermond |
| gen-1143             | NWL LP GOR001A-RMD002A 10 Gbit/s               | rmd002a-rt07, gor001a-rt02                             | Northwind Labs, NWL          | Roermond, Gorinchem |
| gen-1144             | BFH SP TAGGED ASV002A 1 Gbit/s                 | asv002a-rt12                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1148             | RWI IP UTR001A 10 Gbit/s                       | utr001a-rt03                                           | Redwood Institute, RWI       | Utrecht |
| gen-1149             | RWL SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt09                                           | Redwood Libraries, RWL       | Groningen |
| gen-1150             | GFO IP GOR001A 1 Gbit/s                        | gor001a-rt02                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-1151             | BFH SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt10                                           | Bluefin Hospital, BFH        | Roermond |
| gen-1153             | BFH L2VPN MST002A-UTR002A 100 Gbit/s           | utr002a-rt12, utr002a-rt05, mst002a-rt06               | Bluefin Hospital, BFH        | Utrecht, Maastricht |
| gen-1154             | RWL IP RMD002A 1 Gbit/s                        | rmd002a-rt01                                           | Redwood Libraries, RWL       | Roermond |
| gen-1156             | BFU L2VPN ASV001A-ASV002A-GRQ002A 100 Gbit/s   | asv002a-rt01, mst002a-rt08, grq002a-rt04, asv001a-rt03 | Bluefin University, BFU      | Amstelveen, Maastricht, Groningen |
| gen-1157             | GFC L2VPN EHV002A-GRQ001A-UTR002A 100 Gbit/s   | ehv002a-rt07, utr002a-rt02, grq001a-rt12               | Greenfield College, GFC      | Eindhoven, Utrecht, Groningen |
| gen-1158             | GFO SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt05                                           | Greenfield Observatory, GFO  | Enschede |
| gen-1159             | RWI L2VPN ARN002A-RTD002A 100 Gbit/s           | rtd002a-rt12, arn002a-rt02                             | Redwood Institute, RWI       | Rotterdam, Arnhem |
| gen-1160             | RWI LP GRQ001A-MST002A 10 Gbit/s               | grq001a-rt01, mst002a-rt11                             | Redwood Institute, RWI       | Groningen, Maastricht |
| gen-1161             | GFO SP TAGGED MST002A 10 Gbit/s                | mst002a-rt03                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-1162             | SLM IP MST002A 10 Gbit/s                       | mst002a-rt11                                           | Silverline Museum, SLM       | Maastricht |
| gen-1165             | GFC LP GRQ001A-UTR002A 100 Gbit/s              | grq001a-rt11, utr002a-rt02                             | Greenfield College, GFC      | Groningen, Utrecht |
| gen-1166             | RWL LP RMD002A-RTD002A 100 Gbit/s              | rtd002a-rt12, rmd002a-rt05                             | Redwood Libraries, RWL       | Rotterdam, Roermond |
| gen-1169             | GFC L2VPN AMS002A-ASV001A-UTR001A 1 Gbit/s     | utr001a-rt12, asv001a-rt06, ams002a-rt12               | Greenfield College, GFC      | Utrecht, Amstelveen, Amsterdam |
| gen-1170             | BFH SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt11                                           | Bluefin Hospital, BFH        | Enschede |
| gen-1171             | RWI IP GOR002A 10 Gbit/s                       | gor002a-rt06                                           | Redwood Institute, RWI       | Gorinchem |
| gen-1172             | GFC SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt04                                           | Greenfield College, GFC      | Eindhoven |
| gen-1173             | GFO IP RTD001A 10 Gbit/s                       | rtd001a-rt10                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1174             | SLA SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt01                                           | Silverline Archives, SLA     | Arnhem |
| gen-1175             | GFC IP ALM002A 10 Gbit/s                       | alm002a-rt08                                           | Greenfield College, GFC      | Almere |
| gen-1176             | RWI LP ALM002A-GRQ002A 1 Gbit/s                | alm002a-rt12, grq002a-rt04                             | Redwood Institute, RWI       | Almere, Groningen |
| gen-1178             | SLM LP GOR002A-GRQ001A 100 Gbit/s              | gor002a-rt02, grq001a-rt01                             | Silverline Museum, SLM       | Gorinchem, Groningen |
| gen-1179             | GFC SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt03                                           | Greenfield College, GFC      | Gorinchem |
| gen-1180             | GFO LP EHV002A-MST002A 10 Gbit/s               | mst002a-rt06, ehv002a-rt07                             | Greenfield Observatory, GFO  | Maastricht, Eindhoven |
| gen-1181             | BFH IP GOR001A 100 Gbit/s                      | gor001a-rt12                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-1183             | GFC L2VPN AMS002A-GRQ002A-UTR002A 10 Gbit/s    | grq002a-rt08, ams002a-rt06, grq002a-rt07, utr002a-rt11 | Greenfield College, GFC      | Groningen, Amsterdam, Utrecht |
| gen-1184             | SLA SP TAGGED UTR002A 100 Gbit/s               | utr002a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-1185             | NWL SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt01                                           | Northwind Labs, NWL          | Eindhoven |
| gen-1187             | NWR SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt03                                           | Northwind Research, NWR      | Maastricht |
| gen-1188             | GFO LP ARN001A-ENS002A 100 Gbit/s              | arn001a-rt07, ens002a-rt11                             | Greenfield Observatory, GFO  | Arnhem, Enschede |
| gen-1189             | RWI SP TAGGED AMS001A 10 Gbit/s                | ams001a-rt08                                           | Redwood Institute, RWI       | Amsterdam |
| gen-1191             | GFO L2VPN ARN002A-GOR002A 10 Gbit/s            | arn002a-rt10, gor002a-rt10, arn002a-rt03               | Greenfield Observatory, GFO  | Arnhem, Gorinchem |
| gen-1193             | BFU IP EHV002A 100 Gbit/s                      | ehv002a-rt02                                           | Bluefin University, BFU      | Eindhoven |
| gen-1194             | BFH IP ARN002A 100 Gbit/s                      | arn002a-rt02                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-1199             | BFH IP GRQ002A 1 Gbit/s                        | grq002a-rt05                                           | Bluefin Hospital, BFH        | Groningen |
| gen-1200             | GFC IP AMS001A 100 Gbit/s                      | ams001a-rt02                                           | Greenfield College, GFC      | Amsterdam |
| gen-1201             | BFH LP ALM001A-RMD002A 1 Gbit/s                | rmd002a-rt03, alm001a-rt02                             | Bluefin Hospital, BFH        | Roermond, Almere |
| gen-1202             | RWL SP TAGGED GOR002A 100 Gbit/s               | gor002a-rt02                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-1203             | RWI SP UNTAGGED RMD001A 1 Gbit/s               | rmd001a-rt12                                           | Redwood Institute, RWI       | Roermond |
| gen-1204             | GFO SP UNTAGGED ENS001A 100 Gbit/s             | ens001a-rt01                                           | Greenfield Observatory, GFO  | Enschede |
| gen-1205             | BFU SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt07                                           | Bluefin University, BFU      | Roermond |
| gen-1206             | NWR LP ALM001A-GOR001A 100 Gbit/s              | alm001a-rt10, gor001a-rt12                             | Northwind Research, NWR      | Almere, Gorinchem |
| gen-1207             | NWR IP RMD002A 1 Gbit/s                        | rmd002a-rt06                                           | Northwind Research, NWR      | Roermond |
| gen-1209             | GFO IP ARN001A 1 Gbit/s                        | arn001a-rt07                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-1210             | RWL L2VPN EHV002A-MST001A 1 Gbit/s             | ehv002a-rt06, mst001a-rt06                             | Redwood Libraries, RWL       | Eindhoven, Maastricht |
| gen-1211             | SLA SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt03                                           | Silverline Archives, SLA     | Groningen |
| gen-1212             | RWI L2VPN AMS002A-MST001A-MST002A 1 Gbit/s     | mst001a-rt10, ams002a-rt07, mst002a-rt04               | Redwood Institute, RWI       | Maastricht, Amsterdam |
| gen-1213             | GFC SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt03                                           | Greenfield College, GFC      | Arnhem |
| gen-1214             | NWR LP ARN002A-GOR002A 100 Gbit/s              | arn002a-rt02, gor002a-rt01                             | Northwind Research, NWR      | Arnhem, Gorinchem |
| gen-1216             | GFO LP ASV002A-RMD001A 1 Gbit/s                | asv002a-rt11, rmd001a-rt07                             | Greenfield Observatory, GFO  | Amstelveen, Roermond |
| gen-1217             | GFO IP AMS001A 10 Gbit/s                       | ams001a-rt04                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1219             | GFO LP ARN002A-ASV001A 10 Gbit/s               | asv001a-rt09, arn002a-rt02                             | Greenfield Observatory, GFO  | Amstelveen, Arnhem |
| gen-1220             | SLA SP UNTAGGED UTR002A 100 Gbit/s             | utr002a-rt10                                           | Silverline Archives, SLA     | Utrecht |
| gen-1221             | RWI IP ALM001A 10 Gbit/s                       | alm001a-rt11                                           | Redwood Institute, RWI       | Almere |
| gen-1222             | NWL L2VPN ASV001A-ENS002A-GRQ002A 100 Gbit/s   | grq002a-rt09, rmd002a-rt08, asv001a-rt02, ens002a-rt01 | Northwind Labs, NWL          | Groningen, Roermond, Amstelveen, Enschede |
| gen-1224             | BFH IP RMD001A 100 Gbit/s                      | rmd001a-rt03                                           | Bluefin Hospital, BFH        | Roermond |
| gen-1225             | GFC SP UNTAGGED AMS001A 1 Gbit/s               | ams001a-rt02                                           | Greenfield College, GFC      | Amsterdam |
| gen-1226             | RWL SP TAGGED GOR001A 100 Gbit/s               | gor001a-rt02                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-1228             | GFC L2VPN ALM001A-EHV001A-RMD001A 100 Gbit/s   | alm001a-rt05, rmd001a-rt08, rtd002a-rt12, ehv001a-rt02 | Greenfield College, GFC      | Almere, Roermond, Rotterdam, Eindhoven |
| gen-1229             | RWL LP AMS002A-ARN001A 100 Gbit/s              | arn001a-rt06, ams002a-rt11                             | Redwood Libraries, RWL       | Arnhem, Amsterdam |
| gen-1230             | RWL L2VPN ALM001A-ALM002A-RMD001A 10 Gbit/s    | rmd001a-rt08, alm001a-rt06, rmd001a-rt04, alm002a-rt04 | Redwood Libraries, RWL       | Roermond, Almere |
| gen-1232             | NWL L2VPN ASV001A-GRQ001A-MST001A 100 Gbit/s   | asv001a-rt07, grq001a-rt02, mst001a-rt08               | Northwind Labs, NWL          | Amstelveen, Groningen, Maastricht |
| gen-1233             | GFO IP MST002A 100 Gbit/s                      | mst002a-rt03                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-1235             | NWL IP ENS001A 1 Gbit/s                        | ens001a-rt09                                           | Northwind Labs, NWL          | Enschede |
| gen-1236             | BFH SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt03                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-1238             | GFC L2VPN ALM001A-GOR002A-MST001A 1 Gbit/s     | rmd001a-rt12, alm001a-rt10, gor002a-rt08, mst001a-rt10 | Greenfield College, GFC      | Roermond, Almere, Gorinchem, Maastricht |
| gen-1239             | RWI SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt01                                           | Redwood Institute, RWI       | Almere |
| gen-1240             | BFU IP UTR002A 10 Gbit/s                       | utr002a-rt06                                           | Bluefin University, BFU      | Utrecht |
| gen-1244             | BFH LP ENS001A-UTR001A 100 Gbit/s              | utr001a-rt09, ens001a-rt02                             | Bluefin Hospital, BFH        | Utrecht, Enschede |
| gen-1248             | BFU IP UTR002A 1 Gbit/s                        | utr002a-rt12                                           | Bluefin University, BFU      | Utrecht |
| gen-1250             | GFC IP ALM001A 1 Gbit/s                        | alm001a-rt03                                           | Greenfield College, GFC      | Almere |
| gen-1253             | NWL IP MST001A 10 Gbit/s                       | mst001a-rt04                                           | Northwind Labs, NWL          | Maastricht |
| gen-1254             | RWI IP ALM001A 100 Gbit/s                      | alm001a-rt11                                           | Redwood Institute, RWI       | Almere |
| gen-1257             | GFC IP GRQ002A 1 Gbit/s                        | grq002a-rt02                                           | Greenfield College, GFC      | Groningen |
| gen-1261             | RWI SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt05                                           | Redwood Institute, RWI       | Roermond |
| gen-1262             | RWL SP UNTAGGED MST001A 10 Gbit/s              | mst001a-rt11                                           | Redwood Libraries, RWL       | Maastricht |
| gen-1263             | BFH IP ARN001A 100 Gbit/s                      | arn001a-rt04                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-1265             | RWI L2VPN ARN001A-ARN002A-RTD002A 1 Gbit/s     | arn001a-rt02, utr002a-rt12, rtd002a-rt01, arn002a-rt02 | Redwood Institute, RWI       | Arnhem, Utrecht, Rotterdam |
| gen-1266             | GFC LP EHV001A-UTR001A 10 Gbit/s               | utr001a-rt09, ehv001a-rt07                             | Greenfield College, GFC      | Utrecht, Eindhoven |
| gen-1270             | RWL LP ENS001A-RTD001A 1 Gbit/s                | rtd001a-rt11, ens001a-rt08                             | Redwood Libraries, RWL       | Rotterdam, Enschede |
| gen-1271             | GFC LP ASV002A-RTD002A 100 Gbit/s              | asv002a-rt07, rtd002a-rt12                             | Greenfield College, GFC      | Amstelveen, Rotterdam |
| gen-1272             | BFU L2VPN ENS001A-ENS002A 10 Gbit/s            | ens002a-rt08, ens002a-rt04, ens001a-rt05               | Bluefin University, BFU      | Enschede |
| gen-1274             | BFU SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt05                                           | Bluefin University, BFU      | Amstelveen |
| gen-1276             | SLA L2VPN ALM002A-ARN001A-GOR001A 100 Gbit/s   | arn001a-rt10, alm002a-rt08, gor001a-rt08               | Silverline Archives, SLA     | Arnhem, Almere, Gorinchem |
| gen-1277             | RWI SP TAGGED GRQ001A 1 Gbit/s                 | grq001a-rt10                                           | Redwood Institute, RWI       | Groningen |
| gen-1278             | GFO L2VPN ENS001A-UTR002A 100 Gbit/s           | utr002a-rt04, ens001a-rt08                             | Greenfield Observatory, GFO  | Utrecht, Enschede |
| gen-1279             | BFH SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt11                                           | Bluefin Hospital, BFH        | Groningen |
| gen-1281             | SLM IP MST002A 10 Gbit/s                       | mst002a-rt04                                           | Silverline Museum, SLM       | Maastricht |
| gen-1282             | GFO IP AMS002A 10 Gbit/s                       | ams002a-rt12                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1286             | GFC IP RMD001A 10 Gbit/s                       | rmd001a-rt12                                           | Greenfield College, GFC      | Roermond |
| gen-1288             | RWI SP UNTAGGED RMD001A 100 Gbit/s             | rmd001a-rt09                                           | Redwood Institute, RWI       | Roermond |
| gen-1290             | RWI IP RTD002A 1 Gbit/s                        | rtd002a-rt08                                           | Redwood Institute, RWI       | Rotterdam |
| gen-1292             | BFH SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt06                                           | Bluefin Hospital, BFH        | Groningen |
| gen-1293             | RWI SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt06                                           | Redwood Institute, RWI       | Gorinchem |
| gen-1295             | SLA IP ASV001A 10 Gbit/s                       | asv001a-rt11                                           | Silverline Archives, SLA     | Amstelveen |
| gen-1296             | GFO L2VPN ALM002A-ENS001A-MST001A 10 Gbit/s    | ens001a-rt06, mst001a-rt04, alm002a-rt04               | Greenfield Observatory, GFO  | Enschede, Maastricht, Almere |
| gen-1297             | GFO LP ARN001A-ARN002A 1 Gbit/s                | arn002a-rt09, arn001a-rt05                             | Greenfield Observatory, GFO  | Arnhem |
| gen-1298             | BFH IP ALM001A 100 Gbit/s                      | alm001a-rt07                                           | Bluefin Hospital, BFH        | Almere |
| gen-1299             | RWL LP ALM002A-GOR001A 10 Gbit/s               | gor001a-rt06, alm002a-rt10                             | Redwood Libraries, RWL       | Gorinchem, Almere |
| gen-1300             | BFU LP MST002A-UTR002A 100 Gbit/s              | mst002a-rt03, utr002a-rt02                             | Bluefin University, BFU      | Maastricht, Utrecht |
| gen-1304             | RWI LP ARN002A-RTD001A 10 Gbit/s               | rtd001a-rt12, arn002a-rt07                             | Redwood Institute, RWI       | Rotterdam, Arnhem |
| gen-1306             | RWI IP RTD002A 1 Gbit/s                        | rtd002a-rt11                                           | Redwood Institute, RWI       | Rotterdam |
| gen-1307             | GFO LP ASV002A-RTD001A 1 Gbit/s                | rtd001a-rt02, asv002a-rt10                             | Greenfield Observatory, GFO  | Rotterdam, Amstelveen |
| gen-1308             | NWR LP ASV002A-ASV002A 1 Gbit/s                | asv002a-rt01, asv002a-rt06                             | Northwind Research, NWR      | Amstelveen |
| gen-1309             | GFO LP GOR002A-RTD001A 1 Gbit/s                | gor002a-rt10, rtd001a-rt08                             | Greenfield Observatory, GFO  | Gorinchem, Rotterdam |
| gen-1311             | GFO IP ALM002A 1 Gbit/s                        | alm002a-rt08                                           | Greenfield Observatory, GFO  | Almere |
| gen-1312             | GFC SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt07                                           | Greenfield College, GFC      | Maastricht |
| gen-1313             | BFH IP RMD001A 1 Gbit/s                        | rmd001a-rt08                                           | Bluefin Hospital, BFH        | Roermond |
| gen-1314             | RWI LP ARN002A-ENS001A 10 Gbit/s               | ens001a-rt05, arn002a-rt07                             | Redwood Institute, RWI       | Enschede, Arnhem |
| gen-1315             | SLM LP ARN002A-MST001A 10 Gbit/s               | mst001a-rt09, arn002a-rt05                             | Silverline Museum, SLM       | Maastricht, Arnhem |
| gen-1316             | BFU IP ALM002A 1 Gbit/s                        | alm002a-rt04                                           | Bluefin University, BFU      | Almere |
| gen-1317             | RWL L2VPN ALM001A-AMS002A-GOR001A 1 Gbit/s     | ams002a-rt03, alm001a-rt01, gor001a-rt06               | Redwood Libraries, RWL       | Amsterdam, Almere, Gorinchem |
| gen-1318             | GFO SP UNTAGGED AMS002A 10 Gbit/s              | ams002a-rt05                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1321             | GFC SP UNTAGGED GOR001A 10 Gbit/s              | gor001a-rt12                                           | Greenfield College, GFC      | Gorinchem |
| gen-1323             | SLA IP GOR002A 1 Gbit/s                        | gor002a-rt06                                           | Silverline Archives, SLA     | Gorinchem |
| gen-1325             | SLA IP UTR002A 10 Gbit/s                       | utr002a-rt04                                           | Silverline Archives, SLA     | Utrecht |
| gen-1326             | SLM IP ARN001A 10 Gbit/s                       | arn001a-rt10                                           | Silverline Museum, SLM       | Arnhem |
| gen-1329             | GFC L2VPN ARN001A-MST001A-UTR002A 100 Gbit/s   | mst001a-rt10, arn001a-rt04, utr002a-rt10               | Greenfield College, GFC      | Maastricht, Arnhem, Utrecht |
| gen-1330             | SLM SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt01                                           | Silverline Museum, SLM       | Gorinchem |
| gen-1331             | BFU SP UNTAGGED ASV002A 1 Gbit/s               | asv002a-rt05                                           | Bluefin University, BFU      | Amstelveen |
| gen-1332             | RWI LP ALM002A-UTR001A 1 Gbit/s                | alm002a-rt08, utr001a-rt06                             | Redwood Institute, RWI       | Almere, Utrecht |
| gen-1333             | GFO L2VPN EHV002A-UTR001A 10 Gbit/s            | utr001a-rt07, utr001a-rt11, ehv002a-rt06               | Greenfield Observatory, GFO  | Utrecht, Eindhoven |
| gen-1335             | BFU LP ASV001A-RTD002A 1 Gbit/s                | asv001a-rt08, rtd002a-rt12                             | Bluefin University, BFU      | Amstelveen, Rotterdam |
| gen-1336             | RWI LP EHV002A-ENS001A 10 Gbit/s               | ens001a-rt08, ehv002a-rt12                             | Redwood Institute, RWI       | Enschede, Eindhoven |
| gen-1337             | RWL IP AMS002A 10 Gbit/s                       | ams002a-rt11                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-1339             | RWL LP EHV001A-ENS001A 1 Gbit/s                | ens001a-rt12, ehv001a-rt11                             | Redwood Libraries, RWL       | Enschede, Eindhoven |
| gen-1340             | RWI L2VPN GOR001A-GRQ001A-RTD001A 10 Gbit/s    | grq001a-rt11, gor001a-rt09, rtd001a-rt12               | Redwood Institute, RWI       | Groningen, Gorinchem, Rotterdam |
| gen-1341             | RWL LP MST002A-RMD002A 1 Gbit/s                | rmd002a-rt08, mst002a-rt06                             | Redwood Libraries, RWL       | Roermond, Maastricht |
| gen-1342             | NWR IP GRQ002A 1 Gbit/s                        | grq002a-rt03                                           | Northwind Research, NWR      | Groningen |
| gen-1343             | GFC L2VPN AMS001A-AMS002A-ENS002A 1 Gbit/s     | rmd001a-rt08, ams002a-rt05, ens002a-rt10, ams001a-rt03 | Greenfield College, GFC      | Roermond, Amsterdam, Enschede |
| gen-1344             | RWL IP AMS001A 10 Gbit/s                       | ams001a-rt09                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-1345             | SLM SP UNTAGGED AMS001A 10 Gbit/s              | ams001a-rt03                                           | Silverline Museum, SLM       | Amsterdam |
| gen-1346             | BFU LP ARN001A-ARN001A 100 Gbit/s              | arn001a-rt05                                           | Bluefin University, BFU      | Arnhem |
| gen-1348             | SLM SP TAGGED GRQ001A 10 Gbit/s                | grq001a-rt12                                           | Silverline Museum, SLM       | Groningen |
| gen-1349             | GFO IP GRQ002A 1 Gbit/s                        | grq002a-rt04                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1350             | RWI LP AMS002A-UTR001A 100 Gbit/s              | utr001a-rt12, ams002a-rt01                             | Redwood Institute, RWI       | Utrecht, Amsterdam |
| gen-1354             | RWL L2VPN GOR001A-GRQ002A 10 Gbit/s            | grq002a-rt07, gor001a-rt05, grq002a-rt04               | Redwood Libraries, RWL       | Groningen, Gorinchem |
| gen-1356             | RWL L2VPN ALM002A-ARN001A 100 Gbit/s           | alm002a-rt07, arn001a-rt09                             | Redwood Libraries, RWL       | Almere, Arnhem |
| gen-1357             | BFH IP ASV002A 10 Gbit/s                       | asv002a-rt09                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1358             | SLA SP TAGGED AMS001A 100 Gbit/s               | ams001a-rt02                                           | Silverline Archives, SLA     | Amsterdam |
| gen-1359             | BFU L2VPN ARN001A-ASV001A-ENS002A 100 Gbit/s   | utr002a-rt03, ens002a-rt03, arn001a-rt11, asv001a-rt04 | Bluefin University, BFU      | Utrecht, Enschede, Arnhem, Amstelveen |
| gen-1360             | BFH L2VPN ASV002A-GOR002A-GRQ001A 10 Gbit/s    | asv002a-rt04, grq001a-rt07, gor002a-rt08               | Bluefin Hospital, BFH        | Amstelveen, Groningen, Gorinchem |
| gen-1362             | SLA L2VPN ALM002A-ASV001A 100 Gbit/s           | alm002a-rt10, asv001a-rt09                             | Silverline Archives, SLA     | Almere, Amstelveen |
| gen-1365             | NWL LP MST001A-RMD001A 10 Gbit/s               | rmd001a-rt11, mst001a-rt02                             | Northwind Labs, NWL          | Roermond, Maastricht |
| gen-1367             | SLA IP AMS002A 1 Gbit/s                        | ams002a-rt01                                           | Silverline Archives, SLA     | Amsterdam |
| gen-1369             | BFU LP ASV002A-RTD002A 10 Gbit/s               | asv002a-rt05, rtd002a-rt04                             | Bluefin University, BFU      | Amstelveen, Rotterdam |
| gen-1370             | RWL IP UTR001A 100 Gbit/s                      | utr001a-rt04                                           | Redwood Libraries, RWL       | Utrecht |
| gen-1371             | RWI L2VPN ALM001A-RTD002A-UTR001A 10 Gbit/s    | utr002a-rt07, alm001a-rt06, utr001a-rt09, rtd002a-rt06 | Redwood Institute, RWI       | Utrecht, Almere, Rotterdam |
| gen-1373             | BFH IP GOR001A 1 Gbit/s                        | gor001a-rt07                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-1374             | NWR L2VPN ALM001A-ARN001A-ASV001A 10 Gbit/s    | rmd002a-rt05, alm001a-rt06, asv001a-rt09, arn001a-rt11 | Northwind Research, NWR      | Roermond, Almere, Amstelveen, Arnhem |
| gen-1375             | NWR SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt02                                           | Northwind Research, NWR      | Amstelveen |
| gen-1376             | NWR LP GOR001A-GRQ001A 100 Gbit/s              | gor001a-rt12, grq001a-rt12                             | Northwind Research, NWR      | Gorinchem, Groningen |
| gen-1378             | GFO IP EHV002A 10 Gbit/s                       | ehv002a-rt04                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-1379             | NWR SP UNTAGGED MST002A 100 Gbit/s             | mst002a-rt07                                           | Northwind Research, NWR      | Maastricht |
| gen-1381             | BFH IP EHV002A 10 Gbit/s                       | ehv002a-rt12                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1382             | RWI LP ALM002A-ENS002A 10 Gbit/s               | ens002a-rt06, alm002a-rt07                             | Redwood Institute, RWI       | Enschede, Almere |
| gen-1383             | RWI L2VPN ALM001A-ARN001A 100 Gbit/s           | arn001a-rt03, alm001a-rt05                             | Redwood Institute, RWI       | Arnhem, Almere |
| gen-1385             | NWL LP MST001A-MST001A 100 Gbit/s              | mst001a-rt03, mst001a-rt02                             | Northwind Labs, NWL          | Maastricht |
| gen-1386             | RWI L2VPN ARN001A-GOR001A-MST001A 100 Gbit/s   | arn001a-rt04, gor001a-rt07, mst001a-rt10               | Redwood Institute, RWI       | Arnhem, Gorinchem, Maastricht |
| gen-1388             | GFC LP ASV001A-ENS002A 10 Gbit/s               | asv001a-rt11, ens002a-rt03                             | Greenfield College, GFC      | Amstelveen, Enschede |
| gen-1389             | GFC LP ALM001A-ASV001A 1 Gbit/s                | alm001a-rt04, asv001a-rt05                             | Greenfield College, GFC      | Almere, Amstelveen |
| gen-1398             | RWI SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt05                                           | Redwood Institute, RWI       | Almere |
| gen-1401             | GFO SP TAGGED GOR002A 1 Gbit/s                 | gor002a-rt11                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-1402             | BFH IP ENS001A 1 Gbit/s                        | ens001a-rt11                                           | Bluefin Hospital, BFH        | Enschede |
| gen-1403             | NWR SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt06                                           | Northwind Research, NWR      | Eindhoven |
| gen-1405             | GFC LP AMS001A-EHV001A 10 Gbit/s               | ehv001a-rt01, ams001a-rt03                             | Greenfield College, GFC      | Eindhoven, Amsterdam |
| gen-1406             | GFC L2VPN ASV001A-RTD001A 100 Gbit/s           | rtd001a-rt02, asv001a-rt06                             | Greenfield College, GFC      | Rotterdam, Amstelveen |
| gen-1407             | GFO LP ENS001A-MST002A 10 Gbit/s               | ens001a-rt01, mst002a-rt01                             | Greenfield Observatory, GFO  | Enschede, Maastricht |
| gen-1408             | RWL LP MST001A-UTR002A 100 Gbit/s              | utr002a-rt01, mst001a-rt07                             | Redwood Libraries, RWL       | Utrecht, Maastricht |
| gen-1409             | GFO L2VPN ARN001A-EHV002A 100 Gbit/s           | arn001a-rt11, ehv002a-rt06                             | Greenfield Observatory, GFO  | Arnhem, Eindhoven |
| gen-1411             | NWR L2VPN ARN001A-GRQ002A 1 Gbit/s             | grq002a-rt09, arn001a-rt06                             | Northwind Research, NWR      | Groningen, Arnhem |
| gen-1413             | GFC LP RTD001A-UTR001A 100 Gbit/s              | rtd001a-rt02, utr001a-rt03                             | Greenfield College, GFC      | Rotterdam, Utrecht |
| gen-1414             | SLM SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt03                                           | Silverline Museum, SLM       | Almere |
| gen-1415             | SLA IP UTR002A 100 Gbit/s                      | utr002a-rt05                                           | Silverline Archives, SLA     | Utrecht |
| gen-1416             | RWL L2VPN ALM002A-RTD001A 100 Gbit/s           | alm002a-rt05, rtd001a-rt02                             | Redwood Libraries, RWL       | Almere, Rotterdam |
| gen-1417             | NWL LP MST001A-MST002A 100 Gbit/s              | mst002a-rt02, mst001a-rt08                             | Northwind Labs, NWL          | Maastricht |
| gen-1418             | BFH SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt02                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1419             | GFC L2VPN EHV002A-GOR001A-RMD001A 10 Gbit/s    | rmd001a-rt10, ehv002a-rt12, gor001a-rt01               | Greenfield College, GFC      | Roermond, Eindhoven, Gorinchem |
| gen-1420             | BFU IP EHV002A 1 Gbit/s                        | ehv002a-rt12                                           | Bluefin University, BFU      | Eindhoven |
| gen-1423             | BFH SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt02                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-1425             | NWR SP TAGGED MST001A 100 Gbit/s               | mst001a-rt10                                           | Northwind Research, NWR      | Maastricht |
| gen-1426             | RWL IP ENS001A 10 Gbit/s                       | ens001a-rt05                                           | Redwood Libraries, RWL       | Enschede |
| gen-1427             | RWL LP ENS001A-GOR001A 100 Gbit/s              | ens001a-rt12, gor001a-rt03                             | Redwood Libraries, RWL       | Enschede, Gorinchem |
| gen-1429             | SLM IP ALM002A 10 Gbit/s                       | alm002a-rt05                                           | Silverline Museum, SLM       | Almere |
| gen-1433             | BFU IP GOR001A 1 Gbit/s                        | gor001a-rt11                                           | Bluefin University, BFU      | Gorinchem |
| gen-1435             | GFC SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt05                                           | Greenfield College, GFC      | Almere |
| gen-1437             | GFO LP AMS001A-AMS002A 1 Gbit/s                | ams001a-rt06, ams002a-rt01                             | Greenfield Observatory, GFO  | Amsterdam |
| gen-1438             | RWL LP ENS002A-GRQ002A 1 Gbit/s                | grq002a-rt01, ens002a-rt02                             | Redwood Libraries, RWL       | Groningen, Enschede |
| gen-1439             | RWI SP UNTAGGED ARN002A 100 Gbit/s             | arn002a-rt11                                           | Redwood Institute, RWI       | Arnhem |
| gen-1440             | BFH LP ENS002A-GOR002A 100 Gbit/s              | ens002a-rt05, gor002a-rt01                             | Bluefin Hospital, BFH        | Enschede, Gorinchem |
| gen-1441             | GFC SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt05                                           | Greenfield College, GFC      | Roermond |
| gen-1442             | GFO LP ENS002A-UTR001A 1 Gbit/s                | ens002a-rt12, utr001a-rt06                             | Greenfield Observatory, GFO  | Enschede, Utrecht |
| gen-1443             | GFO SP UNTAGGED EHV002A 10 Gbit/s              | ehv002a-rt02                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-1444             | RWI LP RMD001A-RTD002A 10 Gbit/s               | rtd002a-rt12, rmd001a-rt10                             | Redwood Institute, RWI       | Rotterdam, Roermond |
| gen-1446             | BFH IP RTD002A 10 Gbit/s                       | rtd002a-rt05                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-1447             | GFO SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt09                                           | Greenfield Observatory, GFO  | Almere |
| gen-1448             | BFU LP ALM001A-ARN001A 10 Gbit/s               | alm001a-rt03, arn001a-rt09                             | Bluefin University, BFU      | Almere, Arnhem |
| gen-1449             | NWR IP ALM002A 10 Gbit/s                       | alm002a-rt02                                           | Northwind Research, NWR      | Almere |
| gen-1451             | BFU L2VPN ALM002A-ARN002A 10 Gbit/s            | arn002a-rt03, alm002a-rt08                             | Bluefin University, BFU      | Arnhem, Almere |
| gen-1452             | BFH LP EHV001A-UTR002A 10 Gbit/s               | ehv001a-rt09, utr002a-rt02                             | Bluefin Hospital, BFH        | Eindhoven, Utrecht |
| gen-1453             | GFC IP UTR001A 10 Gbit/s                       | utr001a-rt11                                           | Greenfield College, GFC      | Utrecht |
| gen-1455             | NWR L2VPN ALM001A-RMD002A 100 Gbit/s           | rmd002a-rt09, alm001a-rt10                             | Northwind Research, NWR      | Roermond, Almere |
| gen-1456             | SLM IP AMS001A 10 Gbit/s                       | ams001a-rt04                                           | Silverline Museum, SLM       | Amsterdam |
| gen-1459             | RWL LP ALM001A-ENS002A 100 Gbit/s              | alm001a-rt04, ens002a-rt06                             | Redwood Libraries, RWL       | Almere, Enschede |
| gen-1460             | NWR IP ASV001A 1 Gbit/s                        | asv001a-rt02                                           | Northwind Research, NWR      | Amstelveen |
| gen-1463             | BFU LP MST002A-RTD002A 1 Gbit/s                | mst002a-rt03, rtd002a-rt04                             | Bluefin University, BFU      | Maastricht, Rotterdam |
| gen-1464             | GFO SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt06                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-1467             | RWI SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt11                                           | Redwood Institute, RWI       | Almere |
| gen-1469             | BFH SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt07                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1470             | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt12                                           | Greenfield College, GFC      | Enschede |
| gen-1471             | NWR IP ARN002A 1 Gbit/s                        | arn002a-rt01                                           | Northwind Research, NWR      | Arnhem |
| gen-1472             | GFC SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt07                                           | Greenfield College, GFC      | Arnhem |
| gen-1475             | BFH SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt09                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-1480             | RWI LP EHV002A-ENS001A 100 Gbit/s              | ehv002a-rt03, ens001a-rt01                             | Redwood Institute, RWI       | Eindhoven, Enschede |
| gen-1481             | GFC SP TAGGED UTR001A 100 Gbit/s               | utr001a-rt04                                           | Greenfield College, GFC      | Utrecht |
| gen-1486             | GFC IP AMS002A 10 Gbit/s                       | ams002a-rt02                                           | Greenfield College, GFC      | Amsterdam |
| gen-1488             | RWL L2VPN RMD001A-RMD002A-RTD002A 10 Gbit/s    | rmd001a-rt03, rmd001a-rt12, rtd002a-rt07, rmd002a-rt05 | Redwood Libraries, RWL       | Roermond, Rotterdam |
| gen-1489             | BFH LP ARN002A-RMD002A 1 Gbit/s                | arn002a-rt01, rmd002a-rt02                             | Bluefin Hospital, BFH        | Arnhem, Roermond |
| gen-1491             | RWL L2VPN AMS001A-AMS002A-RMD002A 1 Gbit/s     | ams002a-rt01, rmd002a-rt02, ams001a-rt03               | Redwood Libraries, RWL       | Amsterdam, Roermond |
| gen-1492             | RWI IP RTD002A 1 Gbit/s                        | rtd002a-rt10                                           | Redwood Institute, RWI       | Rotterdam |
| gen-1493             | NWR L2VPN ENS001A-GRQ001A 10 Gbit/s            | grq001a-rt05, ens001a-rt12                             | Northwind Research, NWR      | Groningen, Enschede |
| gen-1494             | GFO SP UNTAGGED GOR001A 1 Gbit/s               | gor001a-rt04                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-1495             | RWI L2VPN ARN001A-RMD002A-UTR002A 100 Gbit/s   | rmd002a-rt02, arn001a-rt01, utr002a-rt06               | Redwood Institute, RWI       | Roermond, Arnhem, Utrecht |
| gen-1496             | BFH L2VPN ASV002A-EHV001A 100 Gbit/s           | ehv001a-rt12, asv002a-rt05                             | Bluefin Hospital, BFH        | Eindhoven, Amstelveen |
| gen-1497             | SLM IP ALM001A 10 Gbit/s                       | alm001a-rt01                                           | Silverline Museum, SLM       | Almere |
| gen-1499             | RWI SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt03                                           | Redwood Institute, RWI       | Rotterdam |
| gen-1501             | GFC IP GOR002A 100 Gbit/s                      | gor002a-rt12                                           | Greenfield College, GFC      | Gorinchem |
| gen-1504             | NWL LP ARN001A-RMD001A 100 Gbit/s              | arn001a-rt06, rmd001a-rt06                             | Northwind Labs, NWL          | Arnhem, Roermond |
| gen-1505             | BFH LP EHV001A-MST001A 10 Gbit/s               | ehv001a-rt08, mst001a-rt02                             | Bluefin Hospital, BFH        | Eindhoven, Maastricht |
| gen-1507             | GFC SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt03                                           | Greenfield College, GFC      | Groningen |
| gen-1509             | GFC IP ENS002A 100 Gbit/s                      | ens002a-rt10                                           | Greenfield College, GFC      | Enschede |
| gen-1510             | BFU SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt05                                           | Bluefin University, BFU      | Almere |
| gen-1511             | GFO IP RMD002A 100 Gbit/s                      | rmd002a-rt12                                           | Greenfield Observatory, GFO  | Roermond |
| gen-1512             | GFO IP GRQ002A 1 Gbit/s                        | grq002a-rt06                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1513             | SLM SP UNTAGGED UTR001A 10 Gbit/s              | utr001a-rt11                                           | Silverline Museum, SLM       | Utrecht |
| gen-1515             | GFO L2VPN ASV001A-ENS001A 10 Gbit/s            | asv001a-rt12, ens001a-rt07                             | Greenfield Observatory, GFO  | Amstelveen, Enschede |
| gen-1516             | SLM L2VPN ARN001A-GRQ001A-GRQ002A 100 Gbit/s   | arn001a-rt09, utr001a-rt11, grq002a-rt01, grq001a-rt04 | Silverline Museum, SLM       | Arnhem, Utrecht, Groningen |
| gen-1517             | BFH IP ALM001A 10 Gbit/s                       | alm001a-rt09                                           | Bluefin Hospital, BFH        | Almere |
| gen-1518             | SLA L2VPN ALM002A-MST001A-MST002A 1 Gbit/s     | alm002a-rt09, mst001a-rt08, mst002a-rt08               | Silverline Archives, SLA     | Almere, Maastricht |
| gen-1519             | BFH SP UNTAGGED ASV002A 1 Gbit/s               | asv002a-rt09                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1520             | GFO L2VPN ENS001A-ENS002A-RTD002A 1 Gbit/s     | ens001a-rt10, rtd002a-rt04, ens002a-rt12               | Greenfield Observatory, GFO  | Enschede, Rotterdam |
| gen-1522             | NWR SP TAGGED EHV002A 10 Gbit/s                | ehv002a-rt12                                           | Northwind Research, NWR      | Eindhoven |
| gen-1526             | RWI SP UNTAGGED AMS001A 100 Gbit/s             | ams001a-rt08                                           | Redwood Institute, RWI       | Amsterdam |
| gen-1531             | BFH IP EHV002A 1 Gbit/s                        | ehv002a-rt10                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1532             | NWR L2VPN ENS002A-RMD001A-RMD002A 1 Gbit/s     | ens002a-rt11, rmd001a-rt10, ens002a-rt03, rmd002a-rt08 | Northwind Research, NWR      | Enschede, Roermond |
| gen-1533             | BFU L2VPN ARN001A-ENS001A 10 Gbit/s            | arn001a-rt02, ens001a-rt01                             | Bluefin University, BFU      | Arnhem, Enschede |
| gen-1534             | NWR LP EHV001A-ENS002A 10 Gbit/s               | ens002a-rt08, ehv001a-rt09                             | Northwind Research, NWR      | Enschede, Eindhoven |
| gen-1535             | BFH LP RMD001A-RTD001A 100 Gbit/s              | rtd001a-rt10, rmd001a-rt11                             | Bluefin Hospital, BFH        | Rotterdam, Roermond |
| gen-1538             | RWL IP GOR002A 1 Gbit/s                        | gor002a-rt11                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-1540             | BFH LP EHV001A-UTR002A 10 Gbit/s               | ehv001a-rt07, utr002a-rt11                             | Bluefin Hospital, BFH        | Eindhoven, Utrecht |
| gen-1541             | GFC IP ASV001A 10 Gbit/s                       | asv001a-rt12                                           | Greenfield College, GFC      | Amstelveen |
| gen-1542             | SLM SP UNTAGGED GOR001A 1 Gbit/s               | gor001a-rt05                                           | Silverline Museum, SLM       | Gorinchem |
| gen-1543             | BFU IP ENS002A 10 Gbit/s                       | ens002a-rt02                                           | Bluefin University, BFU      | Enschede |
| gen-1544             | NWR LP ALM001A-ARN002A 100 Gbit/s              | arn002a-rt09, alm001a-rt08                             | Northwind Research, NWR      | Arnhem, Almere |
| gen-1546             | RWL SP UNTAGGED AMS002A 100 Gbit/s             | ams002a-rt05                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-1547             | NWR SP TAGGED MST001A 10 Gbit/s                | mst001a-rt03                                           | Northwind Research, NWR      | Maastricht |
| gen-1549             | SLM L2VPN AMS002A-UTR002A 100 Gbit/s           | ams002a-rt09, utr002a-rt05                             | Silverline Museum, SLM       | Amsterdam, Utrecht |
| gen-1550             | RWL SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt01                                           | Redwood Libraries, RWL       | Almere |
| gen-1551             | NWL LP EHV001A-GOR002A 1 Gbit/s                | gor002a-rt05, ehv001a-rt06                             | Northwind Labs, NWL          | Gorinchem, Eindhoven |
| gen-1552             | BFH SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt03                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-1553             | GFC SP UNTAGGED ENS001A 1 Gbit/s               | ens001a-rt05                                           | Greenfield College, GFC      | Enschede |
| gen-1554             | RWI SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt12                                           | Redwood Institute, RWI       | Maastricht |
| gen-1555             | SLA L2VPN ASV002A 1 Gbit/s                     | asv002a-rt01, asv002a-rt08, asv002a-rt09               | Silverline Archives, SLA     | Amstelveen |
| gen-1556             | GFO LP ASV002A-RMD001A 100 Gbit/s              | rmd001a-rt07, asv002a-rt06                             | Greenfield Observatory, GFO  | Roermond, Amstelveen |
| gen-1557             | GFO SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt08                                           | Greenfield Observatory, GFO  | Roermond |
| gen-1558             | NWL SP TAGGED ARN002A 100 Gbit/s               | arn002a-rt02                                           | Northwind Labs, NWL          | Arnhem |
| gen-1562             | GFO SP TAGGED GRQ001A 1 Gbit/s                 | grq001a-rt01                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1563             | GFC L2VPN ASV002A-ENS002A-UTR001A 100 Gbit/s   | asv002a-rt05, ens002a-rt05, utr001a-rt04               | Greenfield College, GFC      | Amstelveen, Enschede, Utrecht |
| gen-1564             | GFO SP TAGGED MST001A 1 Gbit/s                 | mst001a-rt06                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-1565             | NWR SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt07                                           | Northwind Research, NWR      | Groningen |
| gen-1566             | GFC L2VPN ALM002A-ASV001A-MST001A 100 Gbit/s   | mst001a-rt12, alm002a-rt07, asv001a-rt12, alm002a-rt06 | Greenfield College, GFC      | Maastricht, Almere, Amstelveen |
| gen-1567             | SLM SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt07                                           | Silverline Museum, SLM       | Maastricht |
| gen-1568             | BFH L2VPN EHV001A-EHV002A 100 Gbit/s           | ehv002a-rt02, ehv001a-rt08                             | Bluefin Hospital, BFH        | Eindhoven |
| gen-1570             | GFO LP GRQ001A-UTR002A 100 Gbit/s              | utr002a-rt09, grq001a-rt06                             | Greenfield Observatory, GFO  | Utrecht, Groningen |
| gen-1571             | RWL L2VPN ARN002A-GOR001A-GRQ001A 10 Gbit/s    | arn002a-rt03, gor001a-rt08, grq001a-rt12               | Redwood Libraries, RWL       | Arnhem, Gorinchem, Groningen |
| gen-1572             | RWL IP ARN001A 1 Gbit/s                        | arn001a-rt05                                           | Redwood Libraries, RWL       | Arnhem |
| gen-1575             | NWR LP GOR002A-GRQ002A 100 Gbit/s              | gor002a-rt02, grq002a-rt11                             | Northwind Research, NWR      | Gorinchem, Groningen |
| gen-1576             | RWI LP ARN001A-ARN002A 1 Gbit/s                | arn002a-rt12, arn001a-rt02                             | Redwood Institute, RWI       | Arnhem |
| gen-1577             | GFC LP ALM002A-UTR002A 1 Gbit/s                | alm002a-rt02, utr002a-rt07                             | Greenfield College, GFC      | Almere, Utrecht |
| gen-1578             | GFC IP GOR001A 100 Gbit/s                      | gor001a-rt11                                           | Greenfield College, GFC      | Gorinchem |
| gen-1579             | BFH L2VPN ENS002A-RMD001A-RTD002A 100 Gbit/s   | rtd002a-rt08, ens002a-rt07, rmd001a-rt07               | Bluefin Hospital, BFH        | Rotterdam, Enschede, Roermond |
| gen-1582             | NWR SP TAGGED ASV002A 10 Gbit/s                | asv002a-rt05                                           | Northwind Research, NWR      | Amstelveen |
| gen-1585             | GFC LP ALM002A-GOR001A 100 Gbit/s              | gor001a-rt09, alm002a-rt07                             | Greenfield College, GFC      | Gorinchem, Almere |
| gen-1587             | RWL SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt12                                           | Redwood Libraries, RWL       | Arnhem |
| gen-1589             | BFH IP EHV001A 100 Gbit/s                      | ehv001a-rt10                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1590             | NWR IP EHV001A 100 Gbit/s                      | ehv001a-rt12                                           | Northwind Research, NWR      | Eindhoven |
| gen-1591             | GFC L2VPN ALM001A-EHV001A-ENS002A 10 Gbit/s    | ehv001a-rt07, grq002a-rt05, alm001a-rt01, ens002a-rt10 | Greenfield College, GFC      | Eindhoven, Groningen, Almere, Enschede |
| gen-1593             | RWI L2VPN GOR002A-RTD001A 10 Gbit/s            | rtd001a-rt05, gor002a-rt08                             | Redwood Institute, RWI       | Rotterdam, Gorinchem |
| gen-1595             | GFO L2VPN EHV001A-GOR002A-MST001A 100 Gbit/s   | mst001a-rt08, gor002a-rt03, ehv001a-rt02               | Greenfield Observatory, GFO  | Maastricht, Gorinchem, Eindhoven |
| gen-1596             | BFU IP ENS001A 1 Gbit/s                        | ens001a-rt02                                           | Bluefin University, BFU      | Enschede |
| gen-1597             | BFU SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt07                                           | Bluefin University, BFU      | Eindhoven |
| gen-1598             | BFU IP ENS002A 1 Gbit/s                        | ens002a-rt04                                           | Bluefin University, BFU      | Enschede |
| gen-1599             | NWR IP ALM001A 1 Gbit/s                        | alm001a-rt07                                           | Northwind Research, NWR      | Almere |
| gen-1601             | SLA IP AMS002A 10 Gbit/s                       | ams002a-rt06                                           | Silverline Archives, SLA     | Amsterdam |
| gen-1602             | GFC L2VPN ASV002A-MST001A-RTD001A 10 Gbit/s    | asv002a-rt03, rtd001a-rt10, mst001a-rt10               | Greenfield College, GFC      | Amstelveen, Rotterdam, Maastricht |
| gen-1603             | SLA IP UTR002A 1 Gbit/s                        | utr002a-rt11                                           | Silverline Archives, SLA     | Utrecht |
| gen-1604             | SLA SP TAGGED GRQ002A 100 Gbit/s               | grq002a-rt03                                           | Silverline Archives, SLA     | Groningen |
| gen-1605             | GFC L2VPN ALM002A-ARN001A-MST002A 10 Gbit/s    | alm002a-rt01, mst002a-rt04, arn001a-rt10               | Greenfield College, GFC      | Almere, Maastricht, Arnhem |
| gen-1606             | NWR L2VPN ARN001A-MST001A 100 Gbit/s           | arn001a-rt01, mst001a-rt06, arn001a-rt09               | Northwind Research, NWR      | Arnhem, Maastricht |
| gen-1609             | BFU LP EHV001A-GRQ002A 100 Gbit/s              | ehv001a-rt01, grq002a-rt04                             | Bluefin University, BFU      | Eindhoven, Groningen |
| gen-1610             | GFO IP EHV001A 1 Gbit/s                        | ehv001a-rt10                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-1614             | GFC SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt03                                           | Greenfield College, GFC      | Arnhem |
| gen-1615             | NWL IP RMD002A 100 Gbit/s                      | rmd002a-rt05                                           | Northwind Labs, NWL          | Roermond |
| gen-1616             | SLA L2VPN AMS002A-ASV002A-GOR002A 1 Gbit/s     | ams002a-rt03, gor002a-rt05, asv002a-rt09, ams002a-rt04 | Silverline Archives, SLA     | Amsterdam, Gorinchem, Amstelveen |
| gen-1617             | NWL LP ARN002A-GOR001A 100 Gbit/s              | arn002a-rt01, gor001a-rt01                             | Northwind Labs, NWL          | Arnhem, Gorinchem |
| gen-1618             | GFC LP ALM002A-RMD001A 100 Gbit/s              | rmd001a-rt12, alm002a-rt07                             | Greenfield College, GFC      | Roermond, Almere |
| gen-1619             | RWL LP ARN001A-ENS001A 1 Gbit/s                | ens001a-rt01, arn001a-rt07                             | Redwood Libraries, RWL       | Enschede, Arnhem |
| gen-1621             | NWR IP RMD002A 100 Gbit/s                      | rmd002a-rt08                                           | Northwind Research, NWR      | Roermond |
| gen-1622             | GFO IP AMS001A 100 Gbit/s                      | ams001a-rt05                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1623             | RWI IP UTR001A 100 Gbit/s                      | utr001a-rt05                                           | Redwood Institute, RWI       | Utrecht |
| gen-1624             | BFH LP ALM001A-EHV002A 100 Gbit/s              | alm001a-rt09, ehv002a-rt04                             | Bluefin Hospital, BFH        | Almere, Eindhoven |
| gen-1625             | RWL SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt06                                           | Redwood Libraries, RWL       | Almere |
| gen-1627             | BFH SP TAGGED ALM001A 1 Gbit/s                 | alm001a-rt09                                           | Bluefin Hospital, BFH        | Almere |
| gen-1628             | GFO L2VPN ARN001A-ASV002A-GRQ002A 10 Gbit/s    | grq002a-rt10, rmd002a-rt04, asv002a-rt12, arn001a-rt07 | Greenfield Observatory, GFO  | Groningen, Roermond, Amstelveen, Arnhem |
| gen-1631             | NWR IP GRQ002A 100 Gbit/s                      | grq002a-rt08                                           | Northwind Research, NWR      | Groningen |
| gen-1632             | SLA L2VPN MST001A-UTR002A 1 Gbit/s             | mst001a-rt09, utr002a-rt01                             | Silverline Archives, SLA     | Maastricht, Utrecht |
| gen-1633             | GFC SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt02                                           | Greenfield College, GFC      | Amstelveen |
| gen-1635             | BFH LP RMD001A-RTD001A 10 Gbit/s               | rmd001a-rt06, rtd001a-rt10                             | Bluefin Hospital, BFH        | Roermond, Rotterdam |
| gen-1636             | GFC SP UNTAGGED RTD001A 10 Gbit/s              | rtd001a-rt09                                           | Greenfield College, GFC      | Rotterdam |
| gen-1637             | SLA IP GRQ002A 10 Gbit/s                       | grq002a-rt04                                           | Silverline Archives, SLA     | Groningen |
| gen-1638             | GFO SP UNTAGGED ASV002A 10 Gbit/s              | asv002a-rt01                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-1639             | RWI SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt09                                           | Redwood Institute, RWI       | Arnhem |
| gen-1642             | NWR IP ENS002A 10 Gbit/s                       | ens002a-rt04                                           | Northwind Research, NWR      | Enschede |
| gen-1643             | GFO IP AMS001A 100 Gbit/s                      | ams001a-rt09                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1644             | SLA IP AMS001A 10 Gbit/s                       | ams001a-rt06                                           | Silverline Archives, SLA     | Amsterdam |
| gen-1645             | RWI L2VPN ALM002A-GRQ002A-MST002A 100 Gbit/s   | mst002a-rt03, alm002a-rt12, grq002a-rt06               | Redwood Institute, RWI       | Maastricht, Almere, Groningen |
| gen-1646             | BFU LP ENS002A-UTR001A 10 Gbit/s               | ens002a-rt08, utr001a-rt04                             | Bluefin University, BFU      | Enschede, Utrecht |
| gen-1647             | RWL IP ALM001A 10 Gbit/s                       | alm001a-rt02                                           | Redwood Libraries, RWL       | Almere |
| gen-1649             | SLM SP TAGGED ASV001A 1 Gbit/s                 | asv001a-rt11                                           | Silverline Museum, SLM       | Amstelveen |
| gen-1650             | RWI LP EHV002A-MST002A 1 Gbit/s                | mst002a-rt12, ehv002a-rt02                             | Redwood Institute, RWI       | Maastricht, Eindhoven |
| gen-1651             | GFC L2VPN MST002A-RMD002A-RTD001A 10 Gbit/s    | mst002a-rt12, rtd001a-rt11, rmd002a-rt03               | Greenfield College, GFC      | Maastricht, Rotterdam, Roermond |
| gen-1652             | RWI SP UNTAGGED ENS001A 1 Gbit/s               | ens001a-rt12                                           | Redwood Institute, RWI       | Enschede |
| gen-1653             | BFH IP RTD002A 1 Gbit/s                        | rtd002a-rt10                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-1654             | RWL IP ALM001A 100 Gbit/s                      | alm001a-rt08                                           | Redwood Libraries, RWL       | Almere |
| gen-1655             | GFC SP TAGGED RMD002A 1 Gbit/s                 | rmd002a-rt07                                           | Greenfield College, GFC      | Roermond |
| gen-1656             | BFH IP ALM001A 10 Gbit/s                       | alm001a-rt12                                           | Bluefin Hospital, BFH        | Almere |
| gen-1657             | SLM LP ASV002A-MST002A 10 Gbit/s               | mst002a-rt04, asv002a-rt10                             | Silverline Museum, SLM       | Maastricht, Amstelveen |
| gen-1660             | NWL SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt02                                           | Northwind Labs, NWL          | Amstelveen |
| gen-1662             | GFC L2VPN EHV002A-MST001A-UTR002A 10 Gbit/s    | utr002a-rt02, ehv002a-rt04, mst001a-rt11               | Greenfield College, GFC      | Utrecht, Eindhoven, Maastricht |
| gen-1663             | GFC L2VPN ARN002A-GOR001A-GRQ001A 10 Gbit/s    | arn002a-rt07, grq001a-rt12, mst002a-rt02, gor001a-rt07 | Greenfield College, GFC      | Arnhem, Groningen, Maastricht, Gorinchem |
| gen-1665             | RWL SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt12                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-1666             | BFH IP MST001A 1 Gbit/s                        | mst001a-rt02                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-1669             | RWL LP EHV002A-GRQ002A 1 Gbit/s                | ehv002a-rt10, grq002a-rt02                             | Redwood Libraries, RWL       | Eindhoven, Groningen |
| gen-1670             | NWL L2VPN ASV001A-ASV002A-MST002A 1 Gbit/s     | asv001a-rt07, mst002a-rt11, asv002a-rt01               | Northwind Labs, NWL          | Amstelveen, Maastricht |
| gen-1673             | NWL LP ASV001A-MST002A 1 Gbit/s                | mst002a-rt12, asv001a-rt08                             | Northwind Labs, NWL          | Maastricht, Amstelveen |
| gen-1676             | RWI SP UNTAGGED GRQ001A 1 Gbit/s               | grq001a-rt04                                           | Redwood Institute, RWI       | Groningen |
| gen-1677             | SLM SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt07                                           | Silverline Museum, SLM       | Amstelveen |
| gen-1681             | GFO IP GRQ001A 100 Gbit/s                      | grq001a-rt05                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1682             | NWL L2VPN GRQ002A-RMD002A 100 Gbit/s           | rmd002a-rt04, grq002a-rt01                             | Northwind Labs, NWL          | Roermond, Groningen |
| gen-1686             | GFO L2VPN ARN001A-ENS002A 1 Gbit/s             | ens002a-rt04, arn001a-rt04                             | Greenfield Observatory, GFO  | Enschede, Arnhem |
| gen-1687             | RWL SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt02                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-1691             | GFO LP ENS002A-GRQ001A 100 Gbit/s              | ens002a-rt05, grq001a-rt11                             | Greenfield Observatory, GFO  | Enschede, Groningen |
| gen-1693             | GFO L2VPN ALM002A-EHV002A-RMD002A 10 Gbit/s    | rmd002a-rt07, alm002a-rt10, rtd001a-rt09, ehv002a-rt10 | Greenfield Observatory, GFO  | Roermond, Almere, Rotterdam, Eindhoven |
| gen-1694             | BFU L2VPN ASV002A-RMD002A 1 Gbit/s             | rmd002a-rt12, asv002a-rt05, rmd002a-rt04               | Bluefin University, BFU      | Roermond, Amstelveen |
| gen-1695             | BFH LP GOR002A-MST002A 10 Gbit/s               | gor002a-rt09, mst002a-rt11                             | Bluefin Hospital, BFH        | Gorinchem, Maastricht |
| gen-1696             | RWI LP EHV002A-MST001A 100 Gbit/s              | ehv002a-rt03, mst001a-rt04                             | Redwood Institute, RWI       | Eindhoven, Maastricht |
| gen-1698             | RWI IP RTD001A 10 Gbit/s                       | rtd001a-rt08                                           | Redwood Institute, RWI       | Rotterdam |
| gen-1700             | RWI LP ARN001A-GRQ002A 100 Gbit/s              | grq002a-rt09, arn001a-rt07                             | Redwood Institute, RWI       | Groningen, Arnhem |
| gen-1701             | RWI IP ENS002A 100 Gbit/s                      | ens002a-rt05                                           | Redwood Institute, RWI       | Enschede |
| gen-1702             | RWI LP GOR001A-UTR001A 1 Gbit/s                | utr001a-rt12, gor001a-rt08                             | Redwood Institute, RWI       | Utrecht, Gorinchem |
| gen-1703             | GFO L2VPN ARN001A-GOR002A-MST001A 100 Gbit/s   | rtd002a-rt03, gor002a-rt05, mst001a-rt02, arn001a-rt04 | Greenfield Observatory, GFO  | Rotterdam, Gorinchem, Maastricht, Arnhem |
| gen-1704             | BFU IP ALM002A 10 Gbit/s                       | alm002a-rt10                                           | Bluefin University, BFU      | Almere |
| gen-1705             | GFC IP EHV002A 100 Gbit/s                      | ehv002a-rt07                                           | Greenfield College, GFC      | Eindhoven |
| gen-1708             | BFH SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt04                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-1709             | GFO LP ENS002A-MST001A 1 Gbit/s                | ens002a-rt10, mst001a-rt07                             | Greenfield Observatory, GFO  | Enschede, Maastricht |
| gen-1710             | GFO IP RMD002A 10 Gbit/s                       | rmd002a-rt08                                           | Greenfield Observatory, GFO  | Roermond |
| gen-1711             | RWI LP EHV002A-RTD001A 10 Gbit/s               | ehv002a-rt01, rtd001a-rt06                             | Redwood Institute, RWI       | Eindhoven, Rotterdam |
| gen-1712             | NWR SP TAGGED EHV002A 10 Gbit/s                | ehv002a-rt08                                           | Northwind Research, NWR      | Eindhoven |
| gen-1713             | GFO SP TAGGED AMS002A 10 Gbit/s                | ams002a-rt05                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1714             | NWR IP ASV002A 100 Gbit/s                      | asv002a-rt06                                           | Northwind Research, NWR      | Amstelveen |
| gen-1717             | NWL L2VPN GOR001A-MST002A-RMD001A 10 Gbit/s    | gor001a-rt06, mst002a-rt07, rmd001a-rt03, rmd002a-rt08 | Northwind Labs, NWL          | Gorinchem, Maastricht, Roermond |
| gen-1718             | SLA IP ASV002A 1 Gbit/s                        | asv002a-rt08                                           | Silverline Archives, SLA     | Amstelveen |
| gen-1719             | GFC SP TAGGED UTR002A 1 Gbit/s                 | utr002a-rt06                                           | Greenfield College, GFC      | Utrecht |
| gen-1722             | GFO L2VPN ALM001A-UTR002A 1 Gbit/s             | alm001a-rt01, utr002a-rt07                             | Greenfield Observatory, GFO  | Almere, Utrecht |
| gen-1723             | RWI L2VPN ALM002A-ENS002A-GOR001A 100 Gbit/s   | gor001a-rt09, ens002a-rt04, rmd001a-rt08, alm002a-rt04 | Redwood Institute, RWI       | Gorinchem, Enschede, Roermond, Almere |
| gen-1724             | SLM LP UTR001A-UTR001A 1 Gbit/s                | utr001a-rt07, utr001a-rt03                             | Silverline Museum, SLM       | Utrecht |
| gen-1725             | BFU SP UNTAGGED UTR002A 10 Gbit/s              | utr002a-rt02                                           | Bluefin University, BFU      | Utrecht |
| gen-1726             | BFH SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt03                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1727             | RWI L2VPN GRQ002A-MST001A-RTD001A 100 Gbit/s   | rtd001a-rt12, grq002a-rt12, rtd002a-rt05, mst001a-rt04 | Redwood Institute, RWI       | Rotterdam, Groningen, Maastricht |
| gen-1728             | BFU IP ENS002A 1 Gbit/s                        | ens002a-rt02                                           | Bluefin University, BFU      | Enschede |
| gen-1731             | BFH L2VPN ALM002A-GOR002A-GRQ001A 100 Gbit/s   | alm002a-rt03, grq001a-rt08, gor002a-rt08               | Bluefin Hospital, BFH        | Almere, Groningen, Gorinchem |
| gen-1732             | BFH IP ALM001A 10 Gbit/s                       | alm001a-rt09                                           | Bluefin Hospital, BFH        | Almere |
| gen-1734             | BFH IP RMD002A 100 Gbit/s                      | rmd002a-rt03                                           | Bluefin Hospital, BFH        | Roermond |
| gen-1739             | RWI L2VPN ALM002A-ARN001A 10 Gbit/s            | arn001a-rt12, alm002a-rt08                             | Redwood Institute, RWI       | Arnhem, Almere |
| gen-1742             | SLA LP ALM002A-UTR001A 100 Gbit/s              | utr001a-rt09, alm002a-rt10                             | Silverline Archives, SLA     | Utrecht, Almere |
| gen-1743             | SLA IP ALM002A 10 Gbit/s                       | alm002a-rt04                                           | Silverline Archives, SLA     | Almere |
| gen-1744             | BFU SP UNTAGGED ENS002A 100 Gbit/s             | ens002a-rt03                                           | Bluefin University, BFU      | Enschede |
| gen-1745             | GFC SP TAGGED RTD002A 100 Gbit/s               | rtd002a-rt06                                           | Greenfield College, GFC      | Rotterdam |
| gen-1747             | NWR LP ARN001A-ARN002A 1 Gbit/s                | arn002a-rt12, arn001a-rt10                             | Northwind Research, NWR      | Arnhem |
| gen-1750             | BFH SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt05                                           | Bluefin Hospital, BFH        | Groningen |
| gen-1751             | NWL LP ARN002A-GOR001A 1 Gbit/s                | gor001a-rt03, arn002a-rt09                             | Northwind Labs, NWL          | Gorinchem, Arnhem |
| gen-1753             | NWL IP ENS001A 100 Gbit/s                      | ens001a-rt10                                           | Northwind Labs, NWL          | Enschede |
| gen-1755             | BFU L2VPN EHV002A-MST002A-RMD002A 1 Gbit/s     | ehv002a-rt08, mst002a-rt08, rmd002a-rt02, utr001a-rt03 | Bluefin University, BFU      | Eindhoven, Maastricht, Roermond, Utrecht |
| gen-1756             | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt02                                           | Greenfield College, GFC      | Enschede |
| gen-1757             | NWL L2VPN EHV001A-GRQ002A 1 Gbit/s             | ehv001a-rt07, grq002a-rt09                             | Northwind Labs, NWL          | Eindhoven, Groningen |
| gen-1758             | NWR LP EHV001A-ENS002A 100 Gbit/s              | ehv001a-rt12, ens002a-rt10                             | Northwind Research, NWR      | Eindhoven, Enschede |
| gen-1759             | BFH SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt11                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1760             | RWL IP GOR001A 10 Gbit/s                       | gor001a-rt12                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-1761             | GFC LP ALM002A-ARN001A 100 Gbit/s              | arn001a-rt10, alm002a-rt09                             | Greenfield College, GFC      | Arnhem, Almere |
| gen-1762             | GFO SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt12                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-1763             | NWL SP UNTAGGED MST002A 100 Gbit/s             | mst002a-rt10                                           | Northwind Labs, NWL          | Maastricht |
| gen-1764             | GFO L2VPN EHV002A-GRQ002A-RTD002A 10 Gbit/s    | ehv002a-rt12, ehv002a-rt09, grq002a-rt01, rtd002a-rt03 | Greenfield Observatory, GFO  | Eindhoven, Groningen, Rotterdam |
| gen-1765             | RWL L2VPN ARN001A-MST002A 10 Gbit/s            | arn001a-rt02, mst002a-rt02                             | Redwood Libraries, RWL       | Arnhem, Maastricht |
| gen-1766             | NWL IP ENS001A 10 Gbit/s                       | ens001a-rt04                                           | Northwind Labs, NWL          | Enschede |
| gen-1767             | RWL L2VPN ALM001A-ARN001A-ARN002A 1 Gbit/s     | alm001a-rt12, arn001a-rt09, arn002a-rt02, arn001a-rt07 | Redwood Libraries, RWL       | Almere, Arnhem |
| gen-1768             | NWR SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt11                                           | Northwind Research, NWR      | Almere |
| gen-1773             | RWI IP MST002A 100 Gbit/s                      | mst002a-rt04                                           | Redwood Institute, RWI       | Maastricht |
| gen-1774             | SLA SP UNTAGGED AMS001A 1 Gbit/s               | ams001a-rt03                                           | Silverline Archives, SLA     | Amsterdam |
| gen-1776             | GFO IP ASV002A 10 Gbit/s                       | asv002a-rt03                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-1779             | BFH IP GRQ002A 10 Gbit/s                       | grq002a-rt05                                           | Bluefin Hospital, BFH        | Groningen |
| gen-1781             | NWL IP MST002A 100 Gbit/s                      | mst002a-rt02                                           | Northwind Labs, NWL          | Maastricht |
| gen-1783             | BFH L2VPN ARN002A-EHV001A-GOR002A 100 Gbit/s   | gor002a-rt02, arn002a-rt09, ehv001a-rt07               | Bluefin Hospital, BFH        | Gorinchem, Arnhem, Eindhoven |
| gen-1784             | NWL L2VPN GOR002A-GRQ001A 10 Gbit/s            | grq001a-rt05, gor002a-rt03                             | Northwind Labs, NWL          | Groningen, Gorinchem |
| gen-1786             | GFO IP RTD002A 1 Gbit/s                        | rtd002a-rt06                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1787             | GFO SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt07                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-1788             | RWI L2VPN GOR001A-MST002A 10 Gbit/s            | gor001a-rt06, mst002a-rt11                             | Redwood Institute, RWI       | Gorinchem, Maastricht |
| gen-1790             | RWL SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt02                                           | Redwood Libraries, RWL       | Maastricht |
| gen-1791             | NWL LP MST001A-RMD002A 100 Gbit/s              | rmd002a-rt08, mst001a-rt08                             | Northwind Labs, NWL          | Roermond, Maastricht |
| gen-1792             | SLA IP ARN002A 100 Gbit/s                      | arn002a-rt09                                           | Silverline Archives, SLA     | Arnhem |
| gen-1793             | GFO LP GOR001A-MST001A 100 Gbit/s              | mst001a-rt01, gor001a-rt09                             | Greenfield Observatory, GFO  | Maastricht, Gorinchem |
| gen-1794             | SLM SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt05                                           | Silverline Museum, SLM       | Almere |
| gen-1795             | BFU SP TAGGED EHV002A 10 Gbit/s                | ehv002a-rt11                                           | Bluefin University, BFU      | Eindhoven |
| gen-1797             | NWL L2VPN ARN001A-ASV001A-ENS001A 1 Gbit/s     | arn001a-rt11, asv001a-rt04, ens001a-rt11               | Northwind Labs, NWL          | Arnhem, Amstelveen, Enschede |
| gen-1798             | RWL SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt01                                           | Redwood Libraries, RWL       | Enschede |
| gen-1800             | BFH L2VPN ARN002A-ASV002A-RMD002A 100 Gbit/s   | asv002a-rt12, arn002a-rt06, rmd002a-rt06               | Bluefin Hospital, BFH        | Amstelveen, Arnhem, Roermond |
| gen-1802             | RWL LP ARN001A-EHV001A 1 Gbit/s                | ehv001a-rt01, arn001a-rt09                             | Redwood Libraries, RWL       | Eindhoven, Arnhem |
| gen-1804             | BFU IP GRQ001A 10 Gbit/s                       | grq001a-rt12                                           | Bluefin University, BFU      | Groningen |
| gen-1805             | RWI L2VPN AMS001A-RMD002A 10 Gbit/s            | ams001a-rt04, rmd002a-rt12                             | Redwood Institute, RWI       | Amsterdam, Roermond |
| gen-1807             | SLA IP ASV002A 1 Gbit/s                        | asv002a-rt08                                           | Silverline Archives, SLA     | Amstelveen |
| gen-1812             | SLA IP ALM001A 100 Gbit/s                      | alm001a-rt12                                           | Silverline Archives, SLA     | Almere |
| gen-1813             | BFH LP GOR002A-RMD001A 1 Gbit/s                | rmd001a-rt04, gor002a-rt09                             | Bluefin Hospital, BFH        | Roermond, Gorinchem |
| gen-1815             | GFO SP UNTAGGED RTD001A 10 Gbit/s              | rtd001a-rt04                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1816             | SLM IP AMS002A 100 Gbit/s                      | ams002a-rt11                                           | Silverline Museum, SLM       | Amsterdam |
| gen-1817             | RWL LP ALM001A-EHV001A 10 Gbit/s               | ehv001a-rt04, alm001a-rt10                             | Redwood Libraries, RWL       | Eindhoven, Almere |
| gen-1819             | NWR IP RMD002A 10 Gbit/s                       | rmd002a-rt12                                           | Northwind Research, NWR      | Roermond |
| gen-1821             | BFU L2VPN ALM002A-GOR002A 10 Gbit/s            | alm002a-rt07, gor002a-rt10                             | Bluefin University, BFU      | Almere, Gorinchem |
| gen-1825             | RWL L2VPN EHV002A-ENS001A-GOR002A 100 Gbit/s   | ehv002a-rt12, gor002a-rt05, ens001a-rt12, mst002a-rt07 | Redwood Libraries, RWL       | Eindhoven, Gorinchem, Enschede, Maastricht |
| gen-1827             | NWL IP ALM002A 1 Gbit/s                        | alm002a-rt05                                           | Northwind Labs, NWL          | Almere |
| gen-1832             | GFC LP ARN001A-ENS002A 100 Gbit/s              | arn001a-rt10, ens002a-rt03                             | Greenfield College, GFC      | Arnhem, Enschede |
| gen-1834             | RWL IP ALM001A 10 Gbit/s                       | alm001a-rt07                                           | Redwood Libraries, RWL       | Almere |
| gen-1835             | GFO SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt12                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1836             | NWR SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt06                                           | Northwind Research, NWR      | Maastricht |
| gen-1837             | RWI SP TAGGED ENS001A 10 Gbit/s                | ens001a-rt06                                           | Redwood Institute, RWI       | Enschede |
| gen-1838             | GFC LP ALM001A-ASV002A 1 Gbit/s                | alm001a-rt07, asv002a-rt03                             | Greenfield College, GFC      | Almere, Amstelveen |
| gen-1840             | BFU IP MST002A 10 Gbit/s                       | mst002a-rt10                                           | Bluefin University, BFU      | Maastricht |
| gen-1841             | GFC L2VPN RMD002A 100 Gbit/s                   | rmd002a-rt08, rmd002a-rt04                             | Greenfield College, GFC      | Roermond |
| gen-1842             | NWL L2VPN GRQ001A-RMD002A 1 Gbit/s             | grq001a-rt01, rmd002a-rt12                             | Northwind Labs, NWL          | Groningen, Roermond |
| gen-1843             | RWL L2VPN ARN002A-GRQ001A-RMD002A 100 Gbit/s   | grq001a-rt12, arn002a-rt06, rmd002a-rt04               | Redwood Libraries, RWL       | Groningen, Arnhem, Roermond |
| gen-1844             | GFO L2VPN ALM002A-ASV001A 100 Gbit/s           | alm002a-rt02, asv001a-rt03                             | Greenfield Observatory, GFO  | Almere, Amstelveen |
| gen-1845             | NWR SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt09                                           | Northwind Research, NWR      | Eindhoven |
| gen-1846             | GFC SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt02                                           | Greenfield College, GFC      | Almere |
| gen-1848             | RWL L2VPN ALM001A-ENS002A-RTD002A 100 Gbit/s   | rtd002a-rt03, utr002a-rt02, alm001a-rt03, ens002a-rt09 | Redwood Libraries, RWL       | Rotterdam, Utrecht, Almere, Enschede |
| gen-1851             | SLA SP TAGGED GRQ002A 100 Gbit/s               | grq002a-rt07                                           | Silverline Archives, SLA     | Groningen |
| gen-1853             | NWL LP GRQ001A-RMD001A 100 Gbit/s              | grq001a-rt08, rmd001a-rt02                             | Northwind Labs, NWL          | Groningen, Roermond |
| gen-1856             | RWL LP RMD001A-UTR002A 1 Gbit/s                | rmd001a-rt03, utr002a-rt08                             | Redwood Libraries, RWL       | Roermond, Utrecht |
| gen-1857             | SLA LP ARN001A-GOR002A 1 Gbit/s                | arn001a-rt09, gor002a-rt07                             | Silverline Archives, SLA     | Arnhem, Gorinchem |
| gen-1859             | GFC SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt10                                           | Greenfield College, GFC      | Almere |
| gen-1860             | GFC SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt08                                           | Greenfield College, GFC      | Eindhoven |
| gen-1862             | GFC SP UNTAGGED UTR001A 100 Gbit/s             | utr001a-rt05                                           | Greenfield College, GFC      | Utrecht |
| gen-1866             | BFU SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt11                                           | Bluefin University, BFU      | Eindhoven |
| gen-1868             | BFU L2VPN ALM002A-UTR002A 10 Gbit/s            | alm002a-rt02, utr002a-rt05                             | Bluefin University, BFU      | Almere, Utrecht |
| gen-1869             | RWI IP ARN002A 10 Gbit/s                       | arn002a-rt09                                           | Redwood Institute, RWI       | Arnhem |
| gen-1870             | SLA LP GOR002A-UTR002A 1 Gbit/s                | utr002a-rt04, gor002a-rt10                             | Silverline Archives, SLA     | Utrecht, Gorinchem |
| gen-1871             | NWL L2VPN ALM002A-EHV001A-ENS002A 1 Gbit/s     | alm002a-rt11, grq002a-rt06, ens002a-rt01, ehv001a-rt12 | Northwind Labs, NWL          | Almere, Groningen, Enschede, Eindhoven |
| gen-1872             | NWL LP ALM002A-ASV001A 10 Gbit/s               | alm002a-rt06, asv001a-rt06                             | Northwind Labs, NWL          | Almere, Amstelveen |
| gen-1873             | RWI IP ARN002A 10 Gbit/s                       | arn002a-rt06                                           | Redwood Institute, RWI       | Arnhem |
| gen-1874             | BFU L2VPN ENS001A-RTD001A 100 Gbit/s           | rtd001a-rt06, ens001a-rt06                             | Bluefin University, BFU      | Rotterdam, Enschede |
| gen-1875             | SLA SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt04                                           | Silverline Archives, SLA     | Maastricht |
| gen-1876             | BFU L2VPN ALM001A-UTR002A 1 Gbit/s             | alm001a-rt07, utr002a-rt09                             | Bluefin University, BFU      | Almere, Utrecht |
| gen-1877             | NWL SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt08                                           | Northwind Labs, NWL          | Roermond |
| gen-1880             | RWI SP TAGGED RMD002A 100 Gbit/s               | rmd002a-rt04                                           | Redwood Institute, RWI       | Roermond |
| gen-1884             | GFC L2VPN AMS002A-ASV001A-GOR001A 1 Gbit/s     | ams002a-rt01, mst002a-rt01, gor001a-rt05, asv001a-rt07 | Greenfield College, GFC      | Amsterdam, Maastricht, Gorinchem, Amstelveen |
| gen-1885             | GFC L2VPN ALM001A-MST001A 1 Gbit/s             | mst001a-rt07, alm001a-rt01                             | Greenfield College, GFC      | Maastricht, Almere |
| gen-1886             | RWI IP EHV002A 100 Gbit/s                      | ehv002a-rt07                                           | Redwood Institute, RWI       | Eindhoven |
| gen-1887             | GFC SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt06                                           | Greenfield College, GFC      | Groningen |
| gen-1888             | BFH SP TAGGED UTR001A 10 Gbit/s                | utr001a-rt10                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-1889             | RWI IP ARN001A 10 Gbit/s                       | arn001a-rt04                                           | Redwood Institute, RWI       | Arnhem |
| gen-1890             | GFO SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt12                                           | Greenfield Observatory, GFO  | Roermond |
| gen-1891             | BFU SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt06                                           | Bluefin University, BFU      | Enschede |
| gen-1893             | RWI SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt07                                           | Redwood Institute, RWI       | Eindhoven |
| gen-1894             | RWI L2VPN ALM002A-ARN001A 100 Gbit/s           | alm002a-rt01, arn001a-rt07                             | Redwood Institute, RWI       | Almere, Arnhem |
| gen-1895             | GFC SP TAGGED MST002A 10 Gbit/s                | mst002a-rt06                                           | Greenfield College, GFC      | Maastricht |
| gen-1896             | BFH IP GRQ002A 1 Gbit/s                        | grq002a-rt06                                           | Bluefin Hospital, BFH        | Groningen |
| gen-1897             | SLA IP UTR001A 100 Gbit/s                      | utr001a-rt05                                           | Silverline Archives, SLA     | Utrecht |
| gen-1899             | RWL IP UTR002A 100 Gbit/s                      | utr002a-rt12                                           | Redwood Libraries, RWL       | Utrecht |
| gen-1901             | BFH SP TAGGED RTD001A 1 Gbit/s                 | rtd001a-rt09                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-1902             | GFC LP ALM002A-ENS001A 100 Gbit/s              | ens001a-rt01, alm002a-rt10                             | Greenfield College, GFC      | Enschede, Almere |
| gen-1904             | RWL IP AMS002A 10 Gbit/s                       | ams002a-rt05                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-1905             | SLA SP TAGGED MST001A 100 Gbit/s               | mst001a-rt01                                           | Silverline Archives, SLA     | Maastricht |
| gen-1907             | GFC LP ENS001A-RTD001A 1 Gbit/s                | rtd001a-rt04, ens001a-rt09                             | Greenfield College, GFC      | Rotterdam, Enschede |
| gen-1908             | RWI LP MST002A-RMD002A 10 Gbit/s               | rmd002a-rt01, mst002a-rt06                             | Redwood Institute, RWI       | Roermond, Maastricht |
| gen-1909             | GFC L2VPN ALM002A-GOR002A 10 Gbit/s            | alm002a-rt06, gor002a-rt09                             | Greenfield College, GFC      | Almere, Gorinchem |
| gen-1910             | GFO SP TAGGED MST001A 10 Gbit/s                | mst001a-rt08                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-1913             | GFO IP GRQ002A 10 Gbit/s                       | grq002a-rt10                                           | Greenfield Observatory, GFO  | Groningen |
| gen-1914             | RWI L2VPN ARN001A-ENS001A 10 Gbit/s            | arn001a-rt02, ens001a-rt06                             | Redwood Institute, RWI       | Arnhem, Enschede |
| gen-1916             | RWI IP ARN001A 1 Gbit/s                        | arn001a-rt11                                           | Redwood Institute, RWI       | Arnhem |
| gen-1917             | BFH L2VPN EHV001A-ENS002A-MST002A 10 Gbit/s    | mst002a-rt01, rtd002a-rt09, ens002a-rt11, ehv001a-rt02 | Bluefin Hospital, BFH        | Maastricht, Rotterdam, Enschede, Eindhoven |
| gen-1918             | BFH LP ARN001A-ENS001A 1 Gbit/s                | arn001a-rt08, ens001a-rt04                             | Bluefin Hospital, BFH        | Arnhem, Enschede |
| gen-1919             | BFU L2VPN EHV001A-RMD002A 10 Gbit/s            | ehv001a-rt02, rmd002a-rt06                             | Bluefin University, BFU      | Eindhoven, Roermond |
| gen-1920             | SLM IP UTR002A 10 Gbit/s                       | utr002a-rt11                                           | Silverline Museum, SLM       | Utrecht |
| gen-1921             | RWI IP EHV002A 1 Gbit/s                        | ehv002a-rt06                                           | Redwood Institute, RWI       | Eindhoven |
| gen-1922             | RWL L2VPN EHV001A-EHV002A-ENS002A 10 Gbit/s    | ehv002a-rt01, ens002a-rt06, ehv001a-rt06, mst002a-rt10 | Redwood Libraries, RWL       | Eindhoven, Enschede, Maastricht |
| gen-1923             | RWL SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt03                                           | Redwood Libraries, RWL       | Roermond |
| gen-1928             | GFC IP MST001A 1 Gbit/s                        | mst001a-rt08                                           | Greenfield College, GFC      | Maastricht |
| gen-1929             | NWL SP TAGGED GRQ001A 100 Gbit/s               | grq001a-rt03                                           | Northwind Labs, NWL          | Groningen |
| gen-1930             | NWL L2VPN EHV001A-ENS001A 1 Gbit/s             | ens001a-rt09, ehv001a-rt02                             | Northwind Labs, NWL          | Enschede, Eindhoven |
| gen-1932             | BFU SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt08                                           | Bluefin University, BFU      | Roermond |
| gen-1935             | BFH LP ENS002A-MST001A 10 Gbit/s               | ens002a-rt08, mst001a-rt10                             | Bluefin Hospital, BFH        | Enschede, Maastricht |
| gen-1936             | GFO IP RTD001A 100 Gbit/s                      | rtd001a-rt02                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1937             | NWL SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt12                                           | Northwind Labs, NWL          | Arnhem |
| gen-1938             | RWI L2VPN ALM001A-RTD001A 100 Gbit/s           | rtd001a-rt06, alm001a-rt05                             | Redwood Institute, RWI       | Rotterdam, Almere |
| gen-1941             | GFC LP MST002A-RTD001A 100 Gbit/s              | mst002a-rt03, rtd001a-rt06                             | Greenfield College, GFC      | Maastricht, Rotterdam |
| gen-1942             | NWL IP ALM002A 100 Gbit/s                      | alm002a-rt05                                           | Northwind Labs, NWL          | Almere |
| gen-1943             | GFO SP UNTAGGED RTD001A 100 Gbit/s             | rtd001a-rt06                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-1944             | BFH L2VPN GRQ001A-MST001A 10 Gbit/s            | mst001a-rt12, grq001a-rt03                             | Bluefin Hospital, BFH        | Maastricht, Groningen |
| gen-1945             | RWI IP AMS002A 10 Gbit/s                       | ams002a-rt11                                           | Redwood Institute, RWI       | Amsterdam |
| gen-1946             | GFC IP ENS001A 1 Gbit/s                        | ens001a-rt09                                           | Greenfield College, GFC      | Enschede |
| gen-1952             | BFU L2VPN MST002A-RMD002A-UTR001A 1 Gbit/s     | rmd002a-rt11, mst002a-rt01, utr001a-rt11, rmd002a-rt09 | Bluefin University, BFU      | Roermond, Maastricht, Utrecht |
| gen-1954             | RWI L2VPN AMS002A-EHV002A-ENS002A 10 Gbit/s    | ehv002a-rt03, ens002a-rt08, ams002a-rt04               | Redwood Institute, RWI       | Eindhoven, Enschede, Amsterdam |
| gen-1955             | GFO IP UTR001A 10 Gbit/s                       | utr001a-rt11                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-1957             | RWI IP MST001A 100 Gbit/s                      | mst001a-rt09                                           | Redwood Institute, RWI       | Maastricht |
| gen-1961             | GFC LP ARN002A-GOR002A 1 Gbit/s                | arn002a-rt05, gor002a-rt01                             | Greenfield College, GFC      | Arnhem, Gorinchem |
| gen-1963             | RWI L2VPN ALM001A-GOR002A-MST002A 10 Gbit/s    | mst002a-rt02, gor002a-rt10, alm001a-rt12               | Redwood Institute, RWI       | Maastricht, Gorinchem, Almere |
| gen-1964             | NWL IP ARN002A 10 Gbit/s                       | arn002a-rt03                                           | Northwind Labs, NWL          | Arnhem |
| gen-1965             | BFH SP TAGGED ASV002A 100 Gbit/s               | asv002a-rt12                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-1966             | RWI LP ARN002A-RMD002A 1 Gbit/s                | rmd002a-rt05, arn002a-rt11                             | Redwood Institute, RWI       | Roermond, Arnhem |
| gen-1969             | GFO IP UTR002A 1 Gbit/s                        | utr002a-rt11                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-1970             | GFO SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt03                                           | Greenfield Observatory, GFO  | Roermond |
| gen-1971             | SLM IP ALM001A 10 Gbit/s                       | alm001a-rt04                                           | Silverline Museum, SLM       | Almere |
| gen-1972             | RWL IP MST001A 1 Gbit/s                        | mst001a-rt01                                           | Redwood Libraries, RWL       | Maastricht |
| gen-1973             | SLM LP GOR002A-GOR002A 1 Gbit/s                | gor002a-rt04, gor002a-rt09                             | Silverline Museum, SLM       | Gorinchem |
| gen-1975             | GFO SP UNTAGGED AMS002A 1 Gbit/s               | ams002a-rt07                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-1976             | SLM LP ALM001A-ASV002A 100 Gbit/s              | alm001a-rt11, asv002a-rt12                             | Silverline Museum, SLM       | Almere, Amstelveen |
| gen-1977             | NWL SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt06                                           | Northwind Labs, NWL          | Eindhoven |
| gen-1979             | BFH L2VPN EHV001A-ENS001A-RMD002A 10 Gbit/s    | rmd002a-rt10, ens001a-rt06, ehv001a-rt12               | Bluefin Hospital, BFH        | Roermond, Enschede, Eindhoven |
| gen-1980             | BFU LP ENS002A-RMD001A 10 Gbit/s               | ens002a-rt04, rmd001a-rt12                             | Bluefin University, BFU      | Enschede, Roermond |
| gen-1981             | GFC SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt07                                           | Greenfield College, GFC      | Eindhoven |
| gen-1982             | GFC LP ARN001A-ENS002A 1 Gbit/s                | ens002a-rt07, arn001a-rt11                             | Greenfield College, GFC      | Enschede, Arnhem |
| gen-1985             | GFO LP EHV002A-GRQ001A 1 Gbit/s                | grq001a-rt02, ehv002a-rt03                             | Greenfield Observatory, GFO  | Groningen, Eindhoven |
| gen-1986             | GFO SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt01                                           | Greenfield Observatory, GFO  | Almere |
| gen-1990             | GFC L2VPN ALM001A-ENS001A-GRQ002A 10 Gbit/s    | ens001a-rt06, alm001a-rt07, grq002a-rt04, mst001a-rt06 | Greenfield College, GFC      | Enschede, Almere, Groningen, Maastricht |
| gen-1992             | BFH IP EHV002A 10 Gbit/s                       | ehv002a-rt01                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-1993             | RWI SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt02                                           | Redwood Institute, RWI       | Roermond |
| gen-1994             | RWL L2VPN ARN002A-GOR002A-GRQ001A 10 Gbit/s    | arn002a-rt04, utr002a-rt04, gor002a-rt08, grq001a-rt03 | Redwood Libraries, RWL       | Arnhem, Utrecht, Gorinchem, Groningen |
| gen-1997             | NWR LP ARN002A-ASV002A 100 Gbit/s              | asv002a-rt04, arn002a-rt06                             | Northwind Research, NWR      | Amstelveen, Arnhem |
| gen-1998             | BFU SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt08                                           | Bluefin University, BFU      | Eindhoven |
| gen-1999             | BFH SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt12                                           | Bluefin Hospital, BFH        | Enschede |
| gen-2000             | NWR IP GRQ001A 100 Gbit/s                      | grq001a-rt02                                           | Northwind Research, NWR      | Groningen |
| gen-2001             | RWL SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt02                                           | Redwood Libraries, RWL       | Almere |
| gen-2002             | GFC SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt02                                           | Greenfield College, GFC      | Enschede |
| gen-2003             | SLA SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt08                                           | Silverline Archives, SLA     | Almere |
| gen-2004             | BFU LP ENS002A-GRQ002A 100 Gbit/s              | grq002a-rt03, ens002a-rt05                             | Bluefin University, BFU      | Groningen, Enschede |
| gen-2005             | BFH IP GRQ001A 10 Gbit/s                       | grq001a-rt04                                           | Bluefin Hospital, BFH        | Groningen |
| gen-2008             | RWI LP ARN001A-UTR002A 100 Gbit/s              | arn001a-rt11, utr002a-rt07                             | Redwood Institute, RWI       | Arnhem, Utrecht |
| gen-2011             | NWR IP GRQ002A 10 Gbit/s                       | grq002a-rt09                                           | Northwind Research, NWR      | Groningen |
| gen-2012             | BFH IP GOR002A 10 Gbit/s                       | gor002a-rt02                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-2014             | GFC L2VPN GOR001A-GRQ001A-RMD002A 1 Gbit/s     | rmd002a-rt12, grq001a-rt06, gor001a-rt05               | Greenfield College, GFC      | Roermond, Groningen, Gorinchem |
| gen-2016             | GFC L2VPN MST002A-RMD001A 10 Gbit/s            | rmd001a-rt10, mst002a-rt02                             | Greenfield College, GFC      | Roermond, Maastricht |
| gen-2017             | BFH LP GOR002A-RTD001A 100 Gbit/s              | rtd001a-rt04, gor002a-rt05                             | Bluefin Hospital, BFH        | Rotterdam, Gorinchem |
| gen-2020             | BFH LP ARN001A-RMD002A 10 Gbit/s               | rmd002a-rt02, arn001a-rt01                             | Bluefin Hospital, BFH        | Roermond, Arnhem |
| gen-2021             | RWL LP MST002A-UTR001A 10 Gbit/s               | utr001a-rt01, mst002a-rt02                             | Redwood Libraries, RWL       | Utrecht, Maastricht |
| gen-2022             | SLA L2VPN ALM001A-AMS002A-UTR001A 10 Gbit/s    | utr001a-rt03, alm001a-rt09, ams002a-rt08               | Silverline Archives, SLA     | Utrecht, Almere, Amsterdam |
| gen-2024             | RWL LP MST001A-MST002A 100 Gbit/s              | mst002a-rt02, mst001a-rt08                             | Redwood Libraries, RWL       | Maastricht |
| gen-2025             | SLA IP ALM002A 10 Gbit/s                       | alm002a-rt06                                           | Silverline Archives, SLA     | Almere |
| gen-2026             | GFO IP ASV002A 100 Gbit/s                      | asv002a-rt08                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-2029             | GFC LP ASV002A-GRQ002A 10 Gbit/s               | asv002a-rt02, grq002a-rt09                             | Greenfield College, GFC      | Amstelveen, Groningen |
| gen-2030             | RWI LP RMD001A-RTD001A 10 Gbit/s               | rtd001a-rt08, rmd001a-rt11                             | Redwood Institute, RWI       | Rotterdam, Roermond |
| gen-2031             | GFO LP RMD001A-RMD001A 1 Gbit/s                | rmd001a-rt08, rmd001a-rt11                             | Greenfield Observatory, GFO  | Roermond |
| gen-2032             | BFH LP ASV001A-GRQ001A 100 Gbit/s              | asv001a-rt08, grq001a-rt06                             | Bluefin Hospital, BFH        | Amstelveen, Groningen |
| gen-2033             | SLA LP ALM001A-GRQ002A 1 Gbit/s                | alm001a-rt06, grq002a-rt01                             | Silverline Archives, SLA     | Almere, Groningen |
| gen-2036             | RWI LP GOR001A-RTD002A 1 Gbit/s                | rtd002a-rt06, gor001a-rt05                             | Redwood Institute, RWI       | Rotterdam, Gorinchem |
| gen-2037             | RWL IP UTR001A 1 Gbit/s                        | utr001a-rt08                                           | Redwood Libraries, RWL       | Utrecht |
| gen-2039             | GFC L2VPN AMS001A-ARN001A-GOR002A 1 Gbit/s     | utr002a-rt04, ams001a-rt03, arn001a-rt09, gor002a-rt12 | Greenfield College, GFC      | Utrecht, Amsterdam, Arnhem, Gorinchem |
| gen-2040             | GFC LP GOR002A-UTR001A 10 Gbit/s               | utr001a-rt10, gor002a-rt05                             | Greenfield College, GFC      | Utrecht, Gorinchem |
| gen-2041             | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt12                                           | Greenfield College, GFC      | Enschede |
| gen-2043             | NWR LP GOR002A-MST001A 10 Gbit/s               | gor002a-rt10, mst001a-rt07                             | Northwind Research, NWR      | Gorinchem, Maastricht |
| gen-2044             | NWL SP UNTAGGED EHV002A 1 Gbit/s               | ehv002a-rt11                                           | Northwind Labs, NWL          | Eindhoven |
| gen-2045             | BFU LP GRQ001A-MST002A 1 Gbit/s                | grq001a-rt03, mst002a-rt03                             | Bluefin University, BFU      | Groningen, Maastricht |
| gen-2046             | RWL LP ALM002A-EHV002A 100 Gbit/s              | ehv002a-rt01, alm002a-rt07                             | Redwood Libraries, RWL       | Eindhoven, Almere |
| gen-2049             | RWI IP GRQ001A 10 Gbit/s                       | grq001a-rt04                                           | Redwood Institute, RWI       | Groningen |
| gen-2050             | SLM SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt05                                           | Silverline Museum, SLM       | Gorinchem |
| gen-2051             | GFC SP TAGGED GRQ001A 100 Gbit/s               | grq001a-rt08                                           | Greenfield College, GFC      | Groningen |
| gen-2052             | BFU L2VPN ALM002A-GOR002A 10 Gbit/s            | alm002a-rt05, gor002a-rt06                             | Bluefin University, BFU      | Almere, Gorinchem |
| gen-2053             | RWI IP ALM001A 100 Gbit/s                      | alm001a-rt05                                           | Redwood Institute, RWI       | Almere |
| gen-2055             | GFC L2VPN RMD001A-UTR002A 100 Gbit/s           | rmd001a-rt10, utr002a-rt04                             | Greenfield College, GFC      | Roermond, Utrecht |
| gen-2056             | BFU LP ARN002A-MST002A 100 Gbit/s              | arn002a-rt07, mst002a-rt08                             | Bluefin University, BFU      | Arnhem, Maastricht |
| gen-2057             | BFU IP GOR002A 100 Gbit/s                      | gor002a-rt01                                           | Bluefin University, BFU      | Gorinchem |
| gen-2058             | SLM IP ARN001A 10 Gbit/s                       | arn001a-rt05                                           | Silverline Museum, SLM       | Arnhem |
| gen-2059             | GFC SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt01                                           | Greenfield College, GFC      | Almere |
| gen-2060             | GFO L2VPN EHV002A 10 Gbit/s                    | ehv002a-rt06, ehv002a-rt10                             | Greenfield Observatory, GFO  | Eindhoven |
| gen-2064             | NWR SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt12                                           | Northwind Research, NWR      | Eindhoven |
| gen-2065             | RWI IP EHV002A 1 Gbit/s                        | ehv002a-rt12                                           | Redwood Institute, RWI       | Eindhoven |
| gen-2067             | RWL LP AMS001A-UTR002A 100 Gbit/s              | ams001a-rt04, utr002a-rt05                             | Redwood Libraries, RWL       | Amsterdam, Utrecht |
| gen-2069             | NWL SP TAGGED RMD002A 100 Gbit/s               | rmd002a-rt06                                           | Northwind Labs, NWL          | Roermond |
| gen-2070             | RWI LP RTD001A-UTR001A 1 Gbit/s                | utr001a-rt08, rtd001a-rt08                             | Redwood Institute, RWI       | Utrecht, Rotterdam |
| gen-2071             | NWL SP TAGGED GRQ001A 10 Gbit/s                | grq001a-rt05                                           | Northwind Labs, NWL          | Groningen |
| gen-2073             | BFU SP TAGGED UTR002A 1 Gbit/s                 | utr002a-rt07                                           | Bluefin University, BFU      | Utrecht |
| gen-2075             | SLM L2VPN ALM002A-UTR001A 1 Gbit/s             | alm002a-rt07, utr001a-rt10                             | Silverline Museum, SLM       | Almere, Utrecht |
| gen-2078             | GFO L2VPN ARN002A-ENS002A-UTR001A 100 Gbit/s   | ens002a-rt02, utr001a-rt11, arn002a-rt09, utr002a-rt09 | Greenfield Observatory, GFO  | Enschede, Utrecht, Arnhem |
| gen-2079             | GFC L2VPN ALM002A-AMS002A-ARN001A 10 Gbit/s    | alm002a-rt06, arn001a-rt01, ams002a-rt04, mst002a-rt04 | Greenfield College, GFC      | Almere, Arnhem, Amsterdam, Maastricht |
| gen-2083             | RWI IP EHV001A 1 Gbit/s                        | ehv001a-rt11                                           | Redwood Institute, RWI       | Eindhoven |
| gen-2085             | NWR IP MST002A 10 Gbit/s                       | mst002a-rt01                                           | Northwind Research, NWR      | Maastricht |
| gen-2088             | RWL IP RTD001A 100 Gbit/s                      | rtd001a-rt09                                           | Redwood Libraries, RWL       | Rotterdam |
| gen-2093             | NWL LP GRQ001A-GRQ001A 10 Gbit/s               | grq001a-rt04, grq001a-rt07                             | Northwind Labs, NWL          | Groningen |
| gen-2094             | RWL IP ENS001A 10 Gbit/s                       | ens001a-rt05                                           | Redwood Libraries, RWL       | Enschede |
| gen-2096             | GFC IP UTR002A 100 Gbit/s                      | utr002a-rt11                                           | Greenfield College, GFC      | Utrecht |
| gen-2098             | RWL SP TAGGED RTD001A 100 Gbit/s               | rtd001a-rt02                                           | Redwood Libraries, RWL       | Rotterdam |
| gen-2099             | BFU LP ASV001A-EHV001A 100 Gbit/s              | ehv001a-rt11, asv001a-rt07                             | Bluefin University, BFU      | Eindhoven, Amstelveen |
| gen-2100             | SLM L2VPN AMS002A-GOR001A-GOR002A 100 Gbit/s   | gor001a-rt10, grq001a-rt10, ams002a-rt06, gor002a-rt06 | Silverline Museum, SLM       | Gorinchem, Groningen, Amsterdam |
| gen-2101             | BFH LP ENS001A-ENS002A 10 Gbit/s               | ens001a-rt09, ens002a-rt01                             | Bluefin Hospital, BFH        | Enschede |
| gen-2102             | SLM L2VPN ARN002A-ASV002A-GRQ001A 1 Gbit/s     | asv002a-rt09, arn002a-rt11, grq001a-rt09, utr002a-rt09 | Silverline Museum, SLM       | Amstelveen, Arnhem, Groningen, Utrecht |
| gen-2104             | GFO LP AMS002A-ENS002A 100 Gbit/s              | ams002a-rt12, ens002a-rt11                             | Greenfield Observatory, GFO  | Amsterdam, Enschede |
| gen-2105             | NWL IP RMD001A 100 Gbit/s                      | rmd001a-rt06                                           | Northwind Labs, NWL          | Roermond |
| gen-2107             | BFH LP MST001A-RTD002A 10 Gbit/s               | mst001a-rt06, rtd002a-rt11                             | Bluefin Hospital, BFH        | Maastricht, Rotterdam |
| gen-2109             | SLM L2VPN ALM001A-ASV001A 100 Gbit/s           | asv001a-rt12, alm001a-rt09, alm001a-rt04               | Silverline Museum, SLM       | Amstelveen, Almere |
| gen-2110             | BFU SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt04                                           | Bluefin University, BFU      | Enschede |
| gen-2112             | GFO SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt09                                           | Greenfield Observatory, GFO  | Enschede |
| gen-2114             | BFH SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt04                                           | Bluefin Hospital, BFH        | Roermond |
| gen-2115             | BFH IP EHV001A 1 Gbit/s                        | ehv001a-rt12                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2116             | NWL SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt06                                           | Northwind Labs, NWL          | Groningen |
| gen-2117             | BFH SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt03                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2121             | RWI LP AMS002A-GRQ001A 100 Gbit/s              | ams002a-rt08, grq001a-rt08                             | Redwood Institute, RWI       | Amsterdam, Groningen |
| gen-2122             | BFU L2VPN ARN002A-RMD002A 10 Gbit/s            | arn002a-rt09, rmd002a-rt09                             | Bluefin University, BFU      | Arnhem, Roermond |
| gen-2126             | NWL SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt04                                           | Northwind Labs, NWL          | Gorinchem |
| gen-2127             | GFC SP TAGGED GRQ001A 10 Gbit/s                | grq001a-rt08                                           | Greenfield College, GFC      | Groningen |
| gen-2128             | NWL LP EHV001A-MST002A 100 Gbit/s              | mst002a-rt06, ehv001a-rt07                             | Northwind Labs, NWL          | Maastricht, Eindhoven |
| gen-2130             | RWL SP TAGGED ARN002A 100 Gbit/s               | arn002a-rt11                                           | Redwood Libraries, RWL       | Arnhem |
| gen-2131             | NWR L2VPN ARN001A-ASV001A 1 Gbit/s             | asv001a-rt10, arn001a-rt05                             | Northwind Research, NWR      | Amstelveen, Arnhem |
| gen-2138             | BFH SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt03                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-2141             | BFH IP ARN002A 10 Gbit/s                       | arn002a-rt04                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2146             | BFH SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt08                                           | Bluefin Hospital, BFH        | Almere |
| gen-2148             | BFH SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt10                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2151             | GFO SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt02                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-2152             | GFO LP RTD002A-RTD002A 10 Gbit/s               | rtd002a-rt04, rtd002a-rt06                             | Greenfield Observatory, GFO  | Rotterdam |
| gen-2154             | GFC L2VPN AMS001A-ARN001A-GRQ001A 1 Gbit/s     | rmd001a-rt08, grq001a-rt08, ams001a-rt03, arn001a-rt10 | Greenfield College, GFC      | Roermond, Groningen, Amsterdam, Arnhem |
| gen-2155             | BFU IP EHV002A 1 Gbit/s                        | ehv002a-rt02                                           | Bluefin University, BFU      | Eindhoven |
| gen-2156             | BFU LP ARN002A-RMD002A 10 Gbit/s               | arn002a-rt11, rmd002a-rt04                             | Bluefin University, BFU      | Arnhem, Roermond |
| gen-2157             | RWI SP TAGGED ENS001A 10 Gbit/s                | ens001a-rt07                                           | Redwood Institute, RWI       | Enschede |
| gen-2159             | SLA IP MST002A 1 Gbit/s                        | mst002a-rt06                                           | Silverline Archives, SLA     | Maastricht |
| gen-2161             | GFC L2VPN ARN001A-ASV001A-RMD001A 10 Gbit/s    | asv001a-rt03, arn001a-rt03, rmd001a-rt03               | Greenfield College, GFC      | Amstelveen, Arnhem, Roermond |
| gen-2162             | SLA L2VPN AMS002A-GOR002A 1 Gbit/s             | gor002a-rt09, ams002a-rt06                             | Silverline Archives, SLA     | Gorinchem, Amsterdam |
| gen-2163             | SLA L2VPN ARN001A 10 Gbit/s                    | arn001a-rt06, arn001a-rt03                             | Silverline Archives, SLA     | Arnhem |
| gen-2165             | NWL IP RMD002A 10 Gbit/s                       | rmd002a-rt09                                           | Northwind Labs, NWL          | Roermond |
| gen-2167             | GFO SP UNTAGGED EHV002A 1 Gbit/s               | ehv002a-rt03                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-2169             | GFC SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt05                                           | Greenfield College, GFC      | Gorinchem |
| gen-2170             | RWL LP GOR002A-RMD002A 1 Gbit/s                | rmd002a-rt12, gor002a-rt03                             | Redwood Libraries, RWL       | Roermond, Gorinchem |
| gen-2171             | BFH IP ENS002A 1 Gbit/s                        | ens002a-rt09                                           | Bluefin Hospital, BFH        | Enschede |
| gen-2173             | NWR IP RMD002A 10 Gbit/s                       | rmd002a-rt06                                           | Northwind Research, NWR      | Roermond |
| gen-2174             | RWI SP UNTAGGED RTD002A 100 Gbit/s             | rtd002a-rt07                                           | Redwood Institute, RWI       | Rotterdam |
| gen-2175             | NWR SP TAGGED GRQ002A 100 Gbit/s               | grq002a-rt12                                           | Northwind Research, NWR      | Groningen |
| gen-2176             | GFO LP GOR002A-GRQ002A 1 Gbit/s                | gor002a-rt10, grq002a-rt05                             | Greenfield Observatory, GFO  | Gorinchem, Groningen |
| gen-2178             | SLM IP AMS002A 1 Gbit/s                        | ams002a-rt10                                           | Silverline Museum, SLM       | Amsterdam |
| gen-2179             | BFU IP GRQ002A 1 Gbit/s                        | grq002a-rt03                                           | Bluefin University, BFU      | Groningen |
| gen-2181             | BFH IP MST002A 1 Gbit/s                        | mst002a-rt11                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-2182             | NWR L2VPN ASV001A-MST001A 10 Gbit/s            | mst001a-rt01, asv001a-rt11                             | Northwind Research, NWR      | Maastricht, Amstelveen |
| gen-2184             | BFU LP ENS001A-RMD002A 10 Gbit/s               | rmd002a-rt09, ens001a-rt02                             | Bluefin University, BFU      | Roermond, Enschede |
| gen-2186             | SLA IP UTR002A 100 Gbit/s                      | utr002a-rt09                                           | Silverline Archives, SLA     | Utrecht |
| gen-2187             | NWR IP RMD001A 1 Gbit/s                        | rmd001a-rt07                                           | Northwind Research, NWR      | Roermond |
| gen-2189             | RWL LP ALM001A-RMD001A 1 Gbit/s                | rmd001a-rt02, alm001a-rt06                             | Redwood Libraries, RWL       | Roermond, Almere |
| gen-2191             | RWL L2VPN AMS002A-RTD002A 100 Gbit/s           | rtd002a-rt11, ams002a-rt02                             | Redwood Libraries, RWL       | Rotterdam, Amsterdam |
| gen-2192             | NWL SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt01                                           | Northwind Labs, NWL          | Eindhoven |
| gen-2194             | RWL LP AMS001A-MST001A 10 Gbit/s               | ams001a-rt08, mst001a-rt03                             | Redwood Libraries, RWL       | Amsterdam, Maastricht |
| gen-2195             | GFO SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt09                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-2198             | NWR SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt10                                           | Northwind Research, NWR      | Enschede |
| gen-2199             | GFO IP ENS002A 100 Gbit/s                      | ens002a-rt01                                           | Greenfield Observatory, GFO  | Enschede |
| gen-2202             | NWR L2VPN ARN001A-ARN002A-GOR002A 1 Gbit/s     | gor002a-rt09, arn002a-rt08, grq002a-rt08, arn001a-rt04 | Northwind Research, NWR      | Gorinchem, Arnhem, Groningen |
| gen-2203             | NWR IP ASV001A 1 Gbit/s                        | asv001a-rt06                                           | Northwind Research, NWR      | Amstelveen |
| gen-2205             | RWI LP EHV001A-MST002A 10 Gbit/s               | mst002a-rt09, ehv001a-rt06                             | Redwood Institute, RWI       | Maastricht, Eindhoven |
| gen-2210             | GFO IP EHV002A 10 Gbit/s                       | ehv002a-rt10                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-2211             | NWL IP EHV001A 100 Gbit/s                      | ehv001a-rt01                                           | Northwind Labs, NWL          | Eindhoven |
| gen-2212             | SLA IP ASV002A 10 Gbit/s                       | asv002a-rt08                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2214             | RWI LP MST001A-MST002A 10 Gbit/s               | mst001a-rt06, mst002a-rt01                             | Redwood Institute, RWI       | Maastricht |
| gen-2215             | SLA IP ASV002A 1 Gbit/s                        | asv002a-rt04                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2216             | GFO L2VPN ENS002A-GOR002A-UTR002A 10 Gbit/s    | gor002a-rt12, gor002a-rt06, utr002a-rt05, ens002a-rt04 | Greenfield Observatory, GFO  | Gorinchem, Utrecht, Enschede |
| gen-2218             | GFC LP MST001A-UTR002A 1 Gbit/s                | mst001a-rt02, utr002a-rt08                             | Greenfield College, GFC      | Maastricht, Utrecht |
| gen-2219             | BFU LP GOR002A-MST001A 100 Gbit/s              | gor002a-rt05, mst001a-rt11                             | Bluefin University, BFU      | Gorinchem, Maastricht |
| gen-2220             | GFC SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt01                                           | Greenfield College, GFC      | Gorinchem |
| gen-2228             | NWL L2VPN ASV002A-MST001A 1 Gbit/s             | mst001a-rt04, asv002a-rt07                             | Northwind Labs, NWL          | Maastricht, Amstelveen |
| gen-2230             | GFO L2VPN ARN001A-MST001A-RTD002A 10 Gbit/s    | rtd002a-rt06, mst001a-rt04, arn001a-rt05               | Greenfield Observatory, GFO  | Rotterdam, Maastricht, Arnhem |
| gen-2231             | NWR SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt10                                           | Northwind Research, NWR      | Amstelveen |
| gen-2232             | NWR SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt09                                           | Northwind Research, NWR      | Maastricht |
| gen-2233             | RWI IP ALM002A 1 Gbit/s                        | alm002a-rt03                                           | Redwood Institute, RWI       | Almere |
| gen-2234             | NWL SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt02                                           | Northwind Labs, NWL          | Roermond |
| gen-2235             | GFC SP UNTAGGED RMD001A 10 Gbit/s              | rmd001a-rt08                                           | Greenfield College, GFC      | Roermond |
| gen-2239             | GFC SP TAGGED ENS002A 100 Gbit/s               | ens002a-rt08                                           | Greenfield College, GFC      | Enschede |
| gen-2240             | GFO SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt08                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-2246             | RWI SP UNTAGGED UTR002A 1 Gbit/s               | utr002a-rt10                                           | Redwood Institute, RWI       | Utrecht |
| gen-2248             | NWL LP ALM001A-ENS002A 100 Gbit/s              | ens002a-rt02, alm001a-rt01                             | Northwind Labs, NWL          | Enschede, Almere |
| gen-2250             | RWL L2VPN AMS001A-GOR001A-RMD001A 100 Gbit/s   | gor001a-rt11, rmd001a-rt08, ams001a-rt06               | Redwood Libraries, RWL       | Gorinchem, Roermond, Amsterdam |
| gen-2251             | BFH L2VPN ALM001A-EHV001A-EHV002A 100 Gbit/s   | ens001a-rt09, ehv002a-rt01, alm001a-rt03, ehv001a-rt08 | Bluefin Hospital, BFH        | Enschede, Eindhoven, Almere |
| gen-2252             | GFC LP ALM002A-ENS001A 10 Gbit/s               | alm002a-rt07, ens001a-rt07                             | Greenfield College, GFC      | Almere, Enschede |
| gen-2253             | GFO L2VPN ASV001A-MST002A 100 Gbit/s           | asv001a-rt07, mst002a-rt06                             | Greenfield Observatory, GFO  | Amstelveen, Maastricht |
| gen-2255             | BFU L2VPN ARN002A-RTD001A 10 Gbit/s            | rtd001a-rt09, arn002a-rt09                             | Bluefin University, BFU      | Rotterdam, Arnhem |
| gen-2258             | GFO LP EHV001A-RTD001A 1 Gbit/s                | rtd001a-rt12, ehv001a-rt07                             | Greenfield Observatory, GFO  | Rotterdam, Eindhoven |
| gen-2259             | RWI SP UNTAGGED UTR001A 1 Gbit/s               | utr001a-rt10                                           | Redwood Institute, RWI       | Utrecht |
| gen-2260             | GFO LP ALM001A-ASV002A 100 Gbit/s              | alm001a-rt03, asv002a-rt11                             | Greenfield Observatory, GFO  | Almere, Amstelveen |
| gen-2262             | RWL LP ALM001A-MST002A 100 Gbit/s              | mst002a-rt07, alm001a-rt04                             | Redwood Libraries, RWL       | Maastricht, Almere |
| gen-2268             | BFH IP ALM001A 10 Gbit/s                       | alm001a-rt08                                           | Bluefin Hospital, BFH        | Almere |
| gen-2270             | GFO LP ARN002A-UTR002A 100 Gbit/s              | arn002a-rt07, utr002a-rt08                             | Greenfield Observatory, GFO  | Arnhem, Utrecht |
| gen-2273             | NWR L2VPN ALM002A-GOR002A-MST002A 10 Gbit/s    | gor002a-rt03, alm002a-rt03, mst002a-rt03               | Northwind Research, NWR      | Gorinchem, Almere, Maastricht |
| gen-2274             | GFO IP UTR001A 10 Gbit/s                       | utr001a-rt08                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-2275             | RWL L2VPN MST002A-RTD001A 1 Gbit/s             | mst002a-rt02, rtd001a-rt08                             | Redwood Libraries, RWL       | Maastricht, Rotterdam |
| gen-2276             | GFO SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt04                                           | Greenfield Observatory, GFO  | Roermond |
| gen-2277             | RWL L2VPN ALM002A-AMS001A-AMS002A 10 Gbit/s    | alm002a-rt02, ams001a-rt02, ams002a-rt08               | Redwood Libraries, RWL       | Almere, Amsterdam |
| gen-2278             | SLA LP ALM002A-UTR001A 1 Gbit/s                | alm002a-rt11, utr001a-rt08                             | Silverline Archives, SLA     | Almere, Utrecht |
| gen-2279             | BFH LP ALM002A-GRQ001A 100 Gbit/s              | grq001a-rt11, alm002a-rt01                             | Bluefin Hospital, BFH        | Groningen, Almere |
| gen-2281             | BFU LP ALM002A-EHV001A 1 Gbit/s                | alm002a-rt03, ehv001a-rt11                             | Bluefin University, BFU      | Almere, Eindhoven |
| gen-2282             | BFU L2VPN ASV001A-ENS002A-GOR002A 10 Gbit/s    | ens002a-rt02, asv001a-rt06, gor002a-rt09, utr002a-rt09 | Bluefin University, BFU      | Enschede, Amstelveen, Gorinchem, Utrecht |
| gen-2285             | RWI LP EHV001A-RTD002A 10 Gbit/s               | ehv001a-rt09, rtd002a-rt12                             | Redwood Institute, RWI       | Eindhoven, Rotterdam |
| gen-2287             | GFO IP RMD001A 10 Gbit/s                       | rmd001a-rt02                                           | Greenfield Observatory, GFO  | Roermond |
| gen-2288             | BFU SP TAGGED RTD002A 10 Gbit/s                | rtd002a-rt03                                           | Bluefin University, BFU      | Rotterdam |
| gen-2289             | SLA L2VPN ALM002A-AMS001A-GOR001A 10 Gbit/s    | grq002a-rt06, alm002a-rt03, gor001a-rt12, ams001a-rt03 | Silverline Archives, SLA     | Groningen, Almere, Gorinchem, Amsterdam |
| gen-2290             | GFO L2VPN ALM001A-ASV002A-ENS002A 1 Gbit/s     | asv002a-rt06, ens002a-rt09, alm001a-rt01, asv002a-rt03 | Greenfield Observatory, GFO  | Amstelveen, Enschede, Almere |
| gen-2292             | GFO LP ENS001A-RMD002A 10 Gbit/s               | rmd002a-rt02, ens001a-rt08                             | Greenfield Observatory, GFO  | Roermond, Enschede |
| gen-2294             | GFO L2VPN ARN001A-ENS002A-GRQ001A 10 Gbit/s    | utr002a-rt08, arn001a-rt07, ens002a-rt01, grq001a-rt07 | Greenfield Observatory, GFO  | Utrecht, Arnhem, Enschede, Groningen |
| gen-2295             | SLA SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt05                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2297             | GFC IP UTR001A 100 Gbit/s                      | utr001a-rt11                                           | Greenfield College, GFC      | Utrecht |
| gen-2299             | GFC L2VPN ASV002A-MST002A 10 Gbit/s            | mst002a-rt12, asv002a-rt01                             | Greenfield College, GFC      | Maastricht, Amstelveen |
| gen-2301             | RWL L2VPN ARN002A-EHV001A-RTD001A 1 Gbit/s     | arn002a-rt11, ehv001a-rt06, rtd001a-rt03               | Redwood Libraries, RWL       | Arnhem, Eindhoven, Rotterdam |
| gen-2304             | GFO LP ALM001A-GOR001A 10 Gbit/s               | gor001a-rt06, alm001a-rt06                             | Greenfield Observatory, GFO  | Gorinchem, Almere |
| gen-2305             | BFU LP ARN001A-GOR001A 10 Gbit/s               | gor001a-rt09, arn001a-rt01                             | Bluefin University, BFU      | Gorinchem, Arnhem |
| gen-2307             | GFC LP ALM001A-GRQ002A 10 Gbit/s               | alm001a-rt09, grq002a-rt01                             | Greenfield College, GFC      | Almere, Groningen |
| gen-2310             | BFH IP EHV001A 1 Gbit/s                        | ehv001a-rt10                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2312             | BFH IP RTD001A 100 Gbit/s                      | rtd001a-rt06                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-2313             | RWL LP EHV002A-RTD002A 100 Gbit/s              | ehv002a-rt07, rtd002a-rt10                             | Redwood Libraries, RWL       | Eindhoven, Rotterdam |
| gen-2315             | BFH SP TAGGED RTD001A 1 Gbit/s                 | rtd001a-rt12                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-2317             | RWL SP UNTAGGED UTR002A 10 Gbit/s              | utr002a-rt09                                           | Redwood Libraries, RWL       | Utrecht |
| gen-2318             | GFC IP RTD002A 10 Gbit/s                       | rtd002a-rt06                                           | Greenfield College, GFC      | Rotterdam |
| gen-2319             | SLM L2VPN ALM002A-GRQ001A-MST001A 100 Gbit/s   | grq001a-rt12, mst001a-rt02, utr002a-rt10, alm002a-rt07 | Silverline Museum, SLM       | Groningen, Maastricht, Utrecht, Almere |
| gen-2320             | GFO SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt02                                           | Greenfield Observatory, GFO  | Groningen |
| gen-2321             | GFO SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt03                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-2323             | BFU LP ARN002A-GRQ001A 1 Gbit/s                | grq001a-rt06, arn002a-rt06                             | Bluefin University, BFU      | Groningen, Arnhem |
| gen-2325             | SLA IP MST001A 1 Gbit/s                        | mst001a-rt02                                           | Silverline Archives, SLA     | Maastricht |
| gen-2328             | RWI LP GRQ001A-RTD001A 10 Gbit/s               | grq001a-rt11, rtd001a-rt10                             | Redwood Institute, RWI       | Groningen, Rotterdam |
| gen-2329             | BFH SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt09                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2331             | GFO SP UNTAGGED ASV001A 10 Gbit/s              | asv001a-rt04                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-2332             | NWL LP ENS001A-GOR001A 100 Gbit/s              | gor001a-rt07, ens001a-rt05                             | Northwind Labs, NWL          | Gorinchem, Enschede |
| gen-2334             | SLM IP GOR001A 1 Gbit/s                        | gor001a-rt09                                           | Silverline Museum, SLM       | Gorinchem |
| gen-2336             | NWR L2VPN ARN002A-GOR001A 100 Gbit/s           | arn002a-rt02, gor001a-rt11                             | Northwind Research, NWR      | Arnhem, Gorinchem |
| gen-2337             | GFC IP EHV002A 10 Gbit/s                       | ehv002a-rt11                                           | Greenfield College, GFC      | Eindhoven |
| gen-2338             | GFC IP ALM001A 1 Gbit/s                        | alm001a-rt03                                           | Greenfield College, GFC      | Almere |
| gen-2339             | NWR IP GOR001A 10 Gbit/s                       | gor001a-rt12                                           | Northwind Research, NWR      | Gorinchem |
| gen-2343             | GFO SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt08                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-2344             | GFC LP RTD001A-UTR002A 100 Gbit/s              | rtd001a-rt03, utr002a-rt12                             | Greenfield College, GFC      | Rotterdam, Utrecht |
| gen-2346             | BFH SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt10                                           | Bluefin Hospital, BFH        | Groningen |
| gen-2347             | RWI L2VPN EHV001A-EHV002A-GRQ001A 10 Gbit/s    | grq001a-rt08, ehv001a-rt06, ehv002a-rt04               | Redwood Institute, RWI       | Groningen, Eindhoven |
| gen-2348             | NWR SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt12                                           | Northwind Research, NWR      | Roermond |
| gen-2349             | NWL SP TAGGED ASV002A 100 Gbit/s               | asv002a-rt09                                           | Northwind Labs, NWL          | Amstelveen |
| gen-2350             | SLA LP ARN001A-ASV002A 1 Gbit/s                | asv002a-rt11, arn001a-rt05                             | Silverline Archives, SLA     | Amstelveen, Arnhem |
| gen-2352             | BFU SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt02                                           | Bluefin University, BFU      | Eindhoven |
| gen-2354             | RWI L2VPN EHV001A-GOR001A-GRQ002A 1 Gbit/s     | gor001a-rt09, rtd002a-rt05, grq002a-rt06, ehv001a-rt02 | Redwood Institute, RWI       | Gorinchem, Rotterdam, Groningen, Eindhoven |
| gen-2358             | NWL IP ASV002A 10 Gbit/s                       | asv002a-rt09                                           | Northwind Labs, NWL          | Amstelveen |
| gen-2359             | RWI IP ALM002A 100 Gbit/s                      | alm002a-rt01                                           | Redwood Institute, RWI       | Almere |
| gen-2360             | RWI IP RMD001A 10 Gbit/s                       | rmd001a-rt05                                           | Redwood Institute, RWI       | Roermond |
| gen-2361             | GFC IP ARN001A 1 Gbit/s                        | arn001a-rt06                                           | Greenfield College, GFC      | Arnhem |
| gen-2362             | SLM LP AMS002A-UTR002A 100 Gbit/s              | utr002a-rt07, ams002a-rt07                             | Silverline Museum, SLM       | Utrecht, Amsterdam |
| gen-2363             | NWL LP ASV001A-ASV002A 1 Gbit/s                | asv001a-rt12, asv002a-rt02                             | Northwind Labs, NWL          | Amstelveen |
| gen-2365             | BFH IP ARN001A 1 Gbit/s                        | arn001a-rt05                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2366             | RWL L2VPN ENS001A-RTD001A 10 Gbit/s            | ens001a-rt10, rtd001a-rt06                             | Redwood Libraries, RWL       | Enschede, Rotterdam |
| gen-2367             | NWR LP GOR002A-MST002A 100 Gbit/s              | gor002a-rt08, mst002a-rt03                             | Northwind Research, NWR      | Gorinchem, Maastricht |
| gen-2368             | BFH IP RTD002A 100 Gbit/s                      | rtd002a-rt08                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-2372             | RWI LP ALM002A-ARN001A 100 Gbit/s              | arn001a-rt12, alm002a-rt09                             | Redwood Institute, RWI       | Arnhem, Almere |
| gen-2376             | RWL SP TAGGED AMS001A 1 Gbit/s                 | ams001a-rt05                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-2377             | SLA IP ARN002A 10 Gbit/s                       | arn002a-rt06                                           | Silverline Archives, SLA     | Arnhem |
| gen-2379             | RWL LP ALM002A-ARN002A 10 Gbit/s               | arn002a-rt02, alm002a-rt08                             | Redwood Libraries, RWL       | Arnhem, Almere |
| gen-2380             | BFH LP RMD002A-UTR001A 1 Gbit/s                | utr001a-rt06, rmd002a-rt07                             | Bluefin Hospital, BFH        | Utrecht, Roermond |
| gen-2381             | RWL SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-2383             | RWL IP RMD002A 100 Gbit/s                      | rmd002a-rt06                                           | Redwood Libraries, RWL       | Roermond |
| gen-2384             | BFU SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt12                                           | Bluefin University, BFU      | Enschede |
| gen-2387             | GFC L2VPN ASV001A-RMD001A 100 Gbit/s           | rmd001a-rt02, asv001a-rt11                             | Greenfield College, GFC      | Roermond, Amstelveen |
| gen-2389             | SLA IP GRQ001A 1 Gbit/s                        | grq001a-rt02                                           | Silverline Archives, SLA     | Groningen |
| gen-2391             | RWL L2VPN ARN001A-ARN002A 10 Gbit/s            | arn001a-rt09, arn002a-rt02                             | Redwood Libraries, RWL       | Arnhem |
| gen-2392             | GFC LP MST002A-RTD002A 1 Gbit/s                | rtd002a-rt02, mst002a-rt02                             | Greenfield College, GFC      | Rotterdam, Maastricht |
| gen-2394             | GFC LP EHV002A-RMD002A 1 Gbit/s                | ehv002a-rt12, rmd002a-rt12                             | Greenfield College, GFC      | Eindhoven, Roermond |
| gen-2397             | BFH LP RMD002A-UTR002A 1 Gbit/s                | rmd002a-rt08, utr002a-rt07                             | Bluefin Hospital, BFH        | Roermond, Utrecht |
| gen-2400             | GFC LP EHV002A-GRQ002A 1 Gbit/s                | ehv002a-rt01, grq002a-rt04                             | Greenfield College, GFC      | Eindhoven, Groningen |
| gen-2402             | RWL IP GRQ001A 1 Gbit/s                        | grq001a-rt11                                           | Redwood Libraries, RWL       | Groningen |
| gen-2404             | NWL IP ASV002A 10 Gbit/s                       | asv002a-rt03                                           | Northwind Labs, NWL          | Amstelveen |
| gen-2406             | GFC L2VPN ALM001A-RTD001A 10 Gbit/s            | alm001a-rt07, rtd001a-rt12                             | Greenfield College, GFC      | Almere, Rotterdam |
| gen-2407             | NWL SP TAGGED ENS001A 1 Gbit/s                 | ens001a-rt06                                           | Northwind Labs, NWL          | Enschede |
| gen-2408             | BFH IP ARN001A 1 Gbit/s                        | arn001a-rt02                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2409             | GFO LP GRQ001A-MST001A 100 Gbit/s              | mst001a-rt01, grq001a-rt07                             | Greenfield Observatory, GFO  | Maastricht, Groningen |
| gen-2413             | GFO SP TAGGED AMS001A 1 Gbit/s                 | ams001a-rt08                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2414             | GFO IP AMS002A 1 Gbit/s                        | ams002a-rt03                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2415             | GFC SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt07                                           | Greenfield College, GFC      | Almere |
| gen-2417             | GFC SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt12                                           | Greenfield College, GFC      | Enschede |
| gen-2419             | GFO SP UNTAGGED AMS002A 10 Gbit/s              | ams002a-rt07                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2421             | BFH SP TAGGED ALM002A 10 Gbit/s                | alm002a-rt10                                           | Bluefin Hospital, BFH        | Almere |
| gen-2423             | BFH LP GOR001A-MST002A 100 Gbit/s              | mst002a-rt09, gor001a-rt06                             | Bluefin Hospital, BFH        | Maastricht, Gorinchem |
| gen-2425             | SLA L2VPN ASV002A 10 Gbit/s                    | asv002a-rt02, asv002a-rt03                             | Silverline Archives, SLA     | Amstelveen |
| gen-2426             | RWI L2VPN ARN001A-ARN002A-GRQ002A 100 Gbit/s   | grq002a-rt08, arn001a-rt08, arn002a-rt07, arn001a-rt03 | Redwood Institute, RWI       | Groningen, Arnhem |
| gen-2427             | BFU IP UTR002A 100 Gbit/s                      | utr002a-rt06                                           | Bluefin University, BFU      | Utrecht |
| gen-2429             | RWL IP UTR001A 100 Gbit/s                      | utr001a-rt08                                           | Redwood Libraries, RWL       | Utrecht |
| gen-2430             | BFH IP ARN002A 100 Gbit/s                      | arn002a-rt08                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2432             | RWI IP RMD001A 100 Gbit/s                      | rmd001a-rt04                                           | Redwood Institute, RWI       | Roermond |
| gen-2434             | BFU L2VPN ARN002A-GOR001A-GRQ001A 1 Gbit/s     | arn002a-rt04, grq001a-rt02, gor001a-rt07               | Bluefin University, BFU      | Arnhem, Groningen, Gorinchem |
| gen-2435             | RWL SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt12                                           | Redwood Libraries, RWL       | Arnhem |
| gen-2438             | RWI L2VPN ENS002A-GRQ002A-RMD001A 100 Gbit/s   | utr002a-rt01, rmd001a-rt08, grq002a-rt04, ens002a-rt10 | Redwood Institute, RWI       | Utrecht, Roermond, Groningen, Enschede |
| gen-2439             | GFO LP ARN001A-GRQ001A 10 Gbit/s               | grq001a-rt04, arn001a-rt06                             | Greenfield Observatory, GFO  | Groningen, Arnhem |
| gen-2441             | BFH LP ALM002A-EHV002A 100 Gbit/s              | ehv002a-rt04, alm002a-rt10                             | Bluefin Hospital, BFH        | Eindhoven, Almere |
| gen-2442             | NWR IP ENS001A 10 Gbit/s                       | ens001a-rt06                                           | Northwind Research, NWR      | Enschede |
| gen-2443             | NWR SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt04                                           | Northwind Research, NWR      | Maastricht |
| gen-2445             | BFU SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt12                                           | Bluefin University, BFU      | Maastricht |
| gen-2450             | GFO L2VPN ENS001A-GOR002A 1 Gbit/s             | gor002a-rt11, ens001a-rt01                             | Greenfield Observatory, GFO  | Gorinchem, Enschede |
| gen-2451             | GFO SP TAGGED RTD002A 100 Gbit/s               | rtd002a-rt08                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-2453             | GFO IP RTD001A 1 Gbit/s                        | rtd001a-rt12                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-2454             | RWI L2VPN ALM001A-RMD001A 1 Gbit/s             | alm001a-rt10, rmd001a-rt06                             | Redwood Institute, RWI       | Almere, Roermond |
| gen-2455             | NWR SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt11                                           | Northwind Research, NWR      | Almere |
| gen-2456             | SLA SP TAGGED GOR002A 100 Gbit/s               | gor002a-rt11                                           | Silverline Archives, SLA     | Gorinchem |
| gen-2457             | GFO L2VPN ASV002A-ENS001A 100 Gbit/s           | ens001a-rt02, asv002a-rt01                             | Greenfield Observatory, GFO  | Enschede, Amstelveen |
| gen-2458             | RWI L2VPN AMS002A-MST001A 100 Gbit/s           | ams002a-rt02, mst001a-rt10                             | Redwood Institute, RWI       | Amsterdam, Maastricht |
| gen-2459             | GFO LP ALM001A-EHV002A 1 Gbit/s                | alm001a-rt10, ehv002a-rt08                             | Greenfield Observatory, GFO  | Almere, Eindhoven |
| gen-2461             | SLA SP TAGGED ALM001A 1 Gbit/s                 | alm001a-rt11                                           | Silverline Archives, SLA     | Almere |
| gen-2462             | RWL IP ALM002A 1 Gbit/s                        | alm002a-rt02                                           | Redwood Libraries, RWL       | Almere |
| gen-2463             | RWL L2VPN ALM002A-RTD002A 10 Gbit/s            | rtd002a-rt06, alm002a-rt11                             | Redwood Libraries, RWL       | Rotterdam, Almere |
| gen-2465             | GFO IP RMD002A 1 Gbit/s                        | rmd002a-rt03                                           | Greenfield Observatory, GFO  | Roermond |
| gen-2467             | GFO L2VPN EHV001A-GRQ002A-UTR001A 1 Gbit/s     | utr001a-rt11, ehv001a-rt09, grq002a-rt05               | Greenfield Observatory, GFO  | Utrecht, Eindhoven, Groningen |
| gen-2468             | SLA IP ASV002A 100 Gbit/s                      | asv002a-rt02                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2473             | RWL L2VPN ALM002A-GOR002A-UTR001A 10 Gbit/s    | utr001a-rt06, alm002a-rt04, gor002a-rt08               | Redwood Libraries, RWL       | Utrecht, Almere, Gorinchem |
| gen-2474             | GFC LP ARN001A-ASV001A 10 Gbit/s               | arn001a-rt06, asv001a-rt10                             | Greenfield College, GFC      | Arnhem, Amstelveen |
| gen-2475             | NWL SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt05                                           | Northwind Labs, NWL          | Enschede |
| gen-2477             | GFO L2VPN MST001A-UTR002A 10 Gbit/s            | mst001a-rt12, utr002a-rt11                             | Greenfield Observatory, GFO  | Maastricht, Utrecht |
| gen-2479             | BFU IP MST001A 1 Gbit/s                        | mst001a-rt03                                           | Bluefin University, BFU      | Maastricht |
| gen-2482             | BFH IP EHV001A 100 Gbit/s                      | ehv001a-rt06                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2483             | SLA L2VPN AMS002A-UTR002A 1 Gbit/s             | utr002a-rt01, ams002a-rt01                             | Silverline Archives, SLA     | Utrecht, Amsterdam |
| gen-2484             | SLM SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt08                                           | Silverline Museum, SLM       | Maastricht |
| gen-2486             | BFH IP EHV001A 1 Gbit/s                        | ehv001a-rt04                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2489             | GFO LP ALM002A-ARN002A 100 Gbit/s              | arn002a-rt01, alm002a-rt12                             | Greenfield Observatory, GFO  | Arnhem, Almere |
| gen-2491             | RWI IP ARN001A 10 Gbit/s                       | arn001a-rt02                                           | Redwood Institute, RWI       | Arnhem |
| gen-2492             | RWI IP GRQ002A 100 Gbit/s                      | grq002a-rt12                                           | Redwood Institute, RWI       | Groningen |
| gen-2494             | GFO L2VPN ASV002A-EHV002A-ENS002A 1 Gbit/s     | ens002a-rt09, ehv002a-rt11, gor001a-rt12, asv002a-rt05 | Greenfield Observatory, GFO  | Enschede, Eindhoven, Gorinchem, Amstelveen |
| gen-2495             | BFH L2VPN ALM001A-GRQ001A-MST002A 100 Gbit/s   | alm001a-rt11, mst002a-rt11, grq001a-rt05               | Bluefin Hospital, BFH        | Almere, Maastricht, Groningen |
| gen-2499             | SLA IP AMS002A 100 Gbit/s                      | ams002a-rt01                                           | Silverline Archives, SLA     | Amsterdam |
| gen-2501             | NWR SP UNTAGGED RMD001A 10 Gbit/s              | rmd001a-rt12                                           | Northwind Research, NWR      | Roermond |
| gen-2502             | RWL SP TAGGED RTD001A 1 Gbit/s                 | rtd001a-rt02                                           | Redwood Libraries, RWL       | Rotterdam |
| gen-2503             | NWL IP ENS002A 1 Gbit/s                        | ens002a-rt11                                           | Northwind Labs, NWL          | Enschede |
| gen-2504             | GFO LP ALM002A-ASV001A 10 Gbit/s               | asv001a-rt05, alm002a-rt02                             | Greenfield Observatory, GFO  | Amstelveen, Almere |
| gen-2506             | GFO L2VPN ENS002A-UTR002A 100 Gbit/s           | utr002a-rt08, ens002a-rt06                             | Greenfield Observatory, GFO  | Utrecht, Enschede |
| gen-2508             | GFC L2VPN ASV001A-EHV001A-GOR001A 100 Gbit/s   | grq002a-rt07, asv001a-rt08, ehv001a-rt09, gor001a-rt12 | Greenfield College, GFC      | Groningen, Amstelveen, Eindhoven, Gorinchem |
| gen-2509             | GFO L2VPN ALM001A-RTD002A-UTR001A 1 Gbit/s     | alm001a-rt08, utr001a-rt06, rtd002a-rt04               | Greenfield Observatory, GFO  | Almere, Utrecht, Rotterdam |
| gen-2510             | BFH SP UNTAGGED ASV002A 10 Gbit/s              | asv002a-rt02                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-2511             | RWL IP GRQ001A 10 Gbit/s                       | grq001a-rt09                                           | Redwood Libraries, RWL       | Groningen |
| gen-2512             | BFU IP ALM001A 10 Gbit/s                       | alm001a-rt06                                           | Bluefin University, BFU      | Almere |
| gen-2513             | SLA SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt02                                           | Silverline Archives, SLA     | Gorinchem |
| gen-2514             | GFO L2VPN ENS002A-UTR001A 100 Gbit/s           | utr001a-rt04, ens002a-rt10                             | Greenfield Observatory, GFO  | Utrecht, Enschede |
| gen-2517             | RWI L2VPN EHV001A-GRQ002A 10 Gbit/s            | grq002a-rt06, ehv001a-rt08                             | Redwood Institute, RWI       | Groningen, Eindhoven |
| gen-2518             | SLM SP TAGGED MST002A 10 Gbit/s                | mst002a-rt01                                           | Silverline Museum, SLM       | Maastricht |
| gen-2519             | BFU L2VPN EHV002A-GRQ001A 100 Gbit/s           | ehv002a-rt09, grq001a-rt07, ehv002a-rt03               | Bluefin University, BFU      | Eindhoven, Groningen |
| gen-2520             | RWI SP TAGGED GRQ002A 1 Gbit/s                 | grq002a-rt02                                           | Redwood Institute, RWI       | Groningen |
| gen-2521             | NWR LP ALM001A-ALM001A 100 Gbit/s              | alm001a-rt09, alm001a-rt05                             | Northwind Research, NWR      | Almere |
| gen-2522             | GFO L2VPN AMS002A-GOR002A-RMD002A 1 Gbit/s     | rmd002a-rt09, utr002a-rt09, gor002a-rt07, ams002a-rt02 | Greenfield Observatory, GFO  | Roermond, Utrecht, Gorinchem, Amsterdam |
| gen-2523             | BFH SP TAGGED ENS001A 10 Gbit/s                | ens001a-rt12                                           | Bluefin Hospital, BFH        | Enschede |
| gen-2526             | BFU SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt03                                           | Bluefin University, BFU      | Arnhem |
| gen-2527             | SLM L2VPN AMS002A-GRQ002A 10 Gbit/s            | ams002a-rt08, grq002a-rt08                             | Silverline Museum, SLM       | Amsterdam, Groningen |
| gen-2528             | RWL L2VPN ARN002A-ENS002A-MST001A 10 Gbit/s    | arn002a-rt11, ens002a-rt06, mst001a-rt07               | Redwood Libraries, RWL       | Arnhem, Enschede, Maastricht |
| gen-2529             | NWL L2VPN ARN002A-GRQ001A-GRQ002A 1 Gbit/s     | grq002a-rt12, grq001a-rt04, arn002a-rt06               | Northwind Labs, NWL          | Groningen, Arnhem |
| gen-2532             | RWL IP EHV001A 10 Gbit/s                       | ehv001a-rt06                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-2533             | SLM IP GRQ002A 1 Gbit/s                        | grq002a-rt10                                           | Silverline Museum, SLM       | Groningen |
| gen-2534             | BFH SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt01                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-2536             | GFC SP UNTAGGED UTR002A 100 Gbit/s             | utr002a-rt05                                           | Greenfield College, GFC      | Utrecht |
| gen-2537             | SLM IP GRQ002A 10 Gbit/s                       | grq002a-rt07                                           | Silverline Museum, SLM       | Groningen |
| gen-2540             | BFH SP UNTAGGED ARN002A 100 Gbit/s             | arn002a-rt03                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-2541             | GFC IP RMD002A 10 Gbit/s                       | rmd002a-rt07                                           | Greenfield College, GFC      | Roermond |
| gen-2542             | NWR SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt11                                           | Northwind Research, NWR      | Groningen |
| gen-2543             | RWI SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt07                                           | Redwood Institute, RWI       | Almere |
| gen-2544             | GFC LP ASV002A-ENS001A 10 Gbit/s               | ens001a-rt10, asv002a-rt03                             | Greenfield College, GFC      | Enschede, Amstelveen |
| gen-2545             | GFC SP TAGGED UTR001A 100 Gbit/s               | utr001a-rt08                                           | Greenfield College, GFC      | Utrecht |
| gen-2546             | RWL SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt10                                           | Redwood Libraries, RWL       | Almere |
| gen-2547             | BFU SP TAGGED RTD002A 10 Gbit/s                | rtd002a-rt06                                           | Bluefin University, BFU      | Rotterdam |
| gen-2549             | BFU L2VPN ALM002A-EHV001A-GOR001A 1 Gbit/s     | gor001a-rt04, ehv001a-rt07, alm002a-rt08               | Bluefin University, BFU      | Gorinchem, Eindhoven, Almere |
| gen-2550             | BFU IP RMD002A 100 Gbit/s                      | rmd002a-rt10                                           | Bluefin University, BFU      | Roermond |
| gen-2552             | NWL IP MST002A 100 Gbit/s                      | mst002a-rt04                                           | Northwind Labs, NWL          | Maastricht |
| gen-2553             | BFH IP ASV001A 100 Gbit/s                      | asv001a-rt09                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-2555             | GFC L2VPN ALM002A-AMS002A-ASV002A 10 Gbit/s    | alm002a-rt01, asv002a-rt01, ams002a-rt08, ens002a-rt11 | Greenfield College, GFC      | Almere, Amstelveen, Amsterdam, Enschede |
| gen-2556             | GFO IP RTD002A 100 Gbit/s                      | rtd002a-rt08                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-2558             | RWI L2VPN AMS002A-ARN002A-GOR001A 10 Gbit/s    | arn002a-rt03, rtd002a-rt09, gor001a-rt10, ams002a-rt03 | Redwood Institute, RWI       | Arnhem, Rotterdam, Gorinchem, Amsterdam |
| gen-2559             | GFC SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt07                                           | Greenfield College, GFC      | Gorinchem |
| gen-2560             | NWL SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt09                                           | Northwind Labs, NWL          | Almere |
| gen-2563             | GFC SP UNTAGGED ENS002A 100 Gbit/s             | ens002a-rt05                                           | Greenfield College, GFC      | Enschede |
| gen-2566             | GFC IP RTD002A 100 Gbit/s                      | rtd002a-rt10                                           | Greenfield College, GFC      | Rotterdam |
| gen-2567             | BFH SP TAGGED RMD002A 1 Gbit/s                 | rmd002a-rt01                                           | Bluefin Hospital, BFH        | Roermond |
| gen-2568             | RWI SP UNTAGGED ENS002A 10 Gbit/s              | ens002a-rt03                                           | Redwood Institute, RWI       | Enschede |
| gen-2570             | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt10                                           | Greenfield College, GFC      | Enschede |
| gen-2571             | RWI L2VPN GRQ001A-GRQ002A 100 Gbit/s           | grq001a-rt05, grq002a-rt05                             | Redwood Institute, RWI       | Groningen |
| gen-2573             | BFU IP ARN002A 1 Gbit/s                        | arn002a-rt10                                           | Bluefin University, BFU      | Arnhem |
| gen-2577             | SLA SP UNTAGGED GOR001A 10 Gbit/s              | gor001a-rt11                                           | Silverline Archives, SLA     | Gorinchem |
| gen-2578             | SLM IP GRQ002A 10 Gbit/s                       | grq002a-rt12                                           | Silverline Museum, SLM       | Groningen |
| gen-2579             | BFU IP UTR001A 1 Gbit/s                        | utr001a-rt03                                           | Bluefin University, BFU      | Utrecht |
| gen-2580             | SLM L2VPN ARN002A-GOR002A-UTR001A 1 Gbit/s     | utr001a-rt07, gor002a-rt05, arn002a-rt12               | Silverline Museum, SLM       | Utrecht, Gorinchem, Arnhem |
| gen-2581             | BFH IP MST002A 1 Gbit/s                        | mst002a-rt10                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-2582             | RWL L2VPN AMS002A-ENS001A-RTD002A 100 Gbit/s   | utr001a-rt11, ens001a-rt08, rtd002a-rt09, ams002a-rt12 | Redwood Libraries, RWL       | Utrecht, Enschede, Rotterdam, Amsterdam |
| gen-2583             | GFO IP UTR001A 10 Gbit/s                       | utr001a-rt06                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-2587             | SLA IP ARN001A 100 Gbit/s                      | arn001a-rt06                                           | Silverline Archives, SLA     | Arnhem |
| gen-2588             | SLA IP GRQ002A 1 Gbit/s                        | grq002a-rt10                                           | Silverline Archives, SLA     | Groningen |
| gen-2593             | SLM SP UNTAGGED UTR002A 100 Gbit/s             | utr002a-rt06                                           | Silverline Museum, SLM       | Utrecht |
| gen-2594             | BFH SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt01                                           | Bluefin Hospital, BFH        | Roermond |
| gen-2597             | RWL LP GOR001A-MST002A 100 Gbit/s              | gor001a-rt05, mst002a-rt02                             | Redwood Libraries, RWL       | Gorinchem, Maastricht |
| gen-2599             | BFH LP ARN001A-RMD001A 100 Gbit/s              | rmd001a-rt10, arn001a-rt09                             | Bluefin Hospital, BFH        | Roermond, Arnhem |
| gen-2600             | GFO SP TAGGED RTD002A 100 Gbit/s               | rtd002a-rt05                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-2601             | NWR SP TAGGED GOR002A 100 Gbit/s               | gor002a-rt05                                           | Northwind Research, NWR      | Gorinchem |
| gen-2603             | GFC LP ASV001A-ENS002A 100 Gbit/s              | ens002a-rt01, asv001a-rt03                             | Greenfield College, GFC      | Enschede, Amstelveen |
| gen-2604             | BFH L2VPN ALM001A-ASV002A-GOR001A 1 Gbit/s     | asv002a-rt06, gor002a-rt11, alm001a-rt10, gor001a-rt11 | Bluefin Hospital, BFH        | Amstelveen, Gorinchem, Almere |
| gen-2605             | SLA IP ASV002A 100 Gbit/s                      | asv002a-rt08                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2609             | GFC IP AMS001A 10 Gbit/s                       | ams001a-rt04                                           | Greenfield College, GFC      | Amsterdam |
| gen-2611             | RWI LP GOR001A-MST002A 1 Gbit/s                | gor001a-rt04, mst002a-rt11                             | Redwood Institute, RWI       | Gorinchem, Maastricht |
| gen-2612             | RWI SP UNTAGGED ENS002A 100 Gbit/s             | ens002a-rt11                                           | Redwood Institute, RWI       | Enschede |
| gen-2615             | RWL L2VPN ARN001A-ARN002A 1 Gbit/s             | arn002a-rt09, arn001a-rt02                             | Redwood Libraries, RWL       | Arnhem |
| gen-2617             | SLA L2VPN ARN002A-GRQ002A-UTR001A 100 Gbit/s   | grq002a-rt03, utr001a-rt01, arn002a-rt09               | Silverline Archives, SLA     | Groningen, Utrecht, Arnhem |
| gen-2618             | BFH SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt10                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-2619             | GFO L2VPN ALM002A-GOR001A-GRQ001A 10 Gbit/s    | alm002a-rt08, utr001a-rt05, gor001a-rt01, grq001a-rt07 | Greenfield Observatory, GFO  | Almere, Utrecht, Gorinchem, Groningen |
| gen-2622             | RWI LP EHV001A-GRQ001A 10 Gbit/s               | grq001a-rt06, ehv001a-rt12                             | Redwood Institute, RWI       | Groningen, Eindhoven |
| gen-2623             | NWR L2VPN ALM002A-ARN001A 100 Gbit/s           | arn001a-rt12, alm002a-rt03                             | Northwind Research, NWR      | Arnhem, Almere |
| gen-2633             | SLA SP UNTAGGED UTR002A 1 Gbit/s               | utr002a-rt03                                           | Silverline Archives, SLA     | Utrecht |
| gen-2634             | BFU SP UNTAGGED UTR002A 10 Gbit/s              | utr002a-rt03                                           | Bluefin University, BFU      | Utrecht |
| gen-2635             | NWR IP EHV002A 1 Gbit/s                        | ehv002a-rt10                                           | Northwind Research, NWR      | Eindhoven |
| gen-2637             | BFU SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt04                                           | Bluefin University, BFU      | Arnhem |
| gen-2642             | GFC LP ALM001A-UTR002A 1 Gbit/s                | alm001a-rt03, utr002a-rt06                             | Greenfield College, GFC      | Almere, Utrecht |
| gen-2644             | BFH SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt02                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-2645             | BFU SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt12                                           | Bluefin University, BFU      | Roermond |
| gen-2646             | BFU SP TAGGED UTR002A 1 Gbit/s                 | utr002a-rt01                                           | Bluefin University, BFU      | Utrecht |
| gen-2647             | RWL LP ENS002A-GRQ002A 10 Gbit/s               | grq002a-rt07, ens002a-rt10                             | Redwood Libraries, RWL       | Groningen, Enschede |
| gen-2649             | RWL LP MST001A-RMD002A 1 Gbit/s                | rmd002a-rt03, mst001a-rt02                             | Redwood Libraries, RWL       | Roermond, Maastricht |
| gen-2650             | RWI LP EHV002A-ENS001A 1 Gbit/s                | ehv002a-rt09, ens001a-rt06                             | Redwood Institute, RWI       | Eindhoven, Enschede |
| gen-2651             | BFU L2VPN ALM002A-EHV002A-GRQ001A 10 Gbit/s    | grq001a-rt11, ehv002a-rt11, alm002a-rt05               | Bluefin University, BFU      | Groningen, Eindhoven, Almere |
| gen-2652             | SLA SP TAGGED ASV001A 1 Gbit/s                 | asv001a-rt10                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2653             | NWL LP ALM002A-MST002A 100 Gbit/s              | alm002a-rt10, mst002a-rt09                             | Northwind Labs, NWL          | Almere, Maastricht |
| gen-2654             | GFO SP TAGGED MST001A 10 Gbit/s                | mst001a-rt06                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-2656             | GFO SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt07                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-2657             | NWR L2VPN EHV002A-GOR002A 1 Gbit/s             | gor002a-rt06, ehv002a-rt01                             | Northwind Research, NWR      | Gorinchem, Eindhoven |
| gen-2659             | RWI SP TAGGED MST001A 100 Gbit/s               | mst001a-rt07                                           | Redwood Institute, RWI       | Maastricht |
| gen-2663             | BFU SP TAGGED GOR001A 10 Gbit/s                | gor001a-rt08                                           | Bluefin University, BFU      | Gorinchem |
| gen-2664             | BFU LP ALM001A-ASV001A 1 Gbit/s                | asv001a-rt09, alm001a-rt02                             | Bluefin University, BFU      | Amstelveen, Almere |
| gen-2668             | BFH L2VPN ENS002A-UTR002A 10 Gbit/s            | ens002a-rt07, utr002a-rt02                             | Bluefin Hospital, BFH        | Enschede, Utrecht |
| gen-2671             | GFC SP TAGGED ASV002A 1 Gbit/s                 | asv002a-rt02                                           | Greenfield College, GFC      | Amstelveen |
| gen-2672             | RWL L2VPN ENS002A-UTR001A 1 Gbit/s             | ens002a-rt09, utr001a-rt11                             | Redwood Libraries, RWL       | Enschede, Utrecht |
| gen-2675             | RWI SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt09                                           | Redwood Institute, RWI       | Amsterdam |
| gen-2676             | GFC IP GOR002A 100 Gbit/s                      | gor002a-rt09                                           | Greenfield College, GFC      | Gorinchem |
| gen-2677             | BFU IP ASV002A 1 Gbit/s                        | asv002a-rt08                                           | Bluefin University, BFU      | Amstelveen |
| gen-2679             | RWI SP UNTAGGED ARN002A 100 Gbit/s             | arn002a-rt12                                           | Redwood Institute, RWI       | Arnhem |
| gen-2681             | RWI IP GOR002A 10 Gbit/s                       | gor002a-rt07                                           | Redwood Institute, RWI       | Gorinchem |
| gen-2682             | NWL IP GOR002A 100 Gbit/s                      | gor002a-rt03                                           | Northwind Labs, NWL          | Gorinchem |
| gen-2683             | SLA IP UTR002A 10 Gbit/s                       | utr002a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-2685             | SLM IP AMS001A 1 Gbit/s                        | ams001a-rt06                                           | Silverline Museum, SLM       | Amsterdam |
| gen-2688             | RWL LP EHV002A-GOR001A 1 Gbit/s                | ehv002a-rt12, gor001a-rt08                             | Redwood Libraries, RWL       | Eindhoven, Gorinchem |
| gen-2690             | GFC IP ENS001A 100 Gbit/s                      | ens001a-rt11                                           | Greenfield College, GFC      | Enschede |
| gen-2691             | BFU SP UNTAGGED RTD001A 100 Gbit/s             | rtd001a-rt09                                           | Bluefin University, BFU      | Rotterdam |
| gen-2693             | RWL IP UTR002A 10 Gbit/s                       | utr002a-rt01                                           | Redwood Libraries, RWL       | Utrecht |
| gen-2694             | GFO SP UNTAGGED ENS001A 1 Gbit/s               | ens001a-rt01                                           | Greenfield Observatory, GFO  | Enschede |
| gen-2695             | GFO LP ENS001A-GOR001A 10 Gbit/s               | ens001a-rt07, gor001a-rt03                             | Greenfield Observatory, GFO  | Enschede, Gorinchem |
| gen-2696             | NWL LP ENS002A-MST001A 1 Gbit/s                | mst001a-rt09, ens002a-rt10                             | Northwind Labs, NWL          | Maastricht, Enschede |
| gen-2699             | BFU LP GRQ002A-RMD002A 10 Gbit/s               | grq002a-rt12, rmd002a-rt02                             | Bluefin University, BFU      | Groningen, Roermond |
| gen-2700             | SLM SP TAGGED AMS002A 1 Gbit/s                 | ams002a-rt12                                           | Silverline Museum, SLM       | Amsterdam |
| gen-2702             | NWR SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt10                                           | Northwind Research, NWR      | Groningen |
| gen-2703             | SLA SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt09                                           | Silverline Archives, SLA     | Maastricht |
| gen-2705             | RWI SP TAGGED GRQ002A 100 Gbit/s               | grq002a-rt03                                           | Redwood Institute, RWI       | Groningen |
| gen-2706             | RWI IP UTR002A 1 Gbit/s                        | utr002a-rt08                                           | Redwood Institute, RWI       | Utrecht |
| gen-2708             | SLM SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt01                                           | Silverline Museum, SLM       | Amstelveen |
| gen-2710             | GFC LP ALM001A-AMS002A 10 Gbit/s               | ams002a-rt05, alm001a-rt05                             | Greenfield College, GFC      | Amsterdam, Almere |
| gen-2715             | NWR SP UNTAGGED GOR001A 1 Gbit/s               | gor001a-rt10                                           | Northwind Research, NWR      | Gorinchem |
| gen-2717             | RWI L2VPN ARN001A-EHV002A-GOR002A 10 Gbit/s    | gor002a-rt04, ehv002a-rt12, arn001a-rt10               | Redwood Institute, RWI       | Gorinchem, Eindhoven, Arnhem |
| gen-2718             | NWR IP ENS001A 10 Gbit/s                       | ens001a-rt08                                           | Northwind Research, NWR      | Enschede |
| gen-2719             | GFO SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt03                                           | Greenfield Observatory, GFO  | Roermond |
| gen-2721             | NWR SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt11                                           | Northwind Research, NWR      | Roermond |
| gen-2722             | GFO L2VPN ENS002A-MST001A-RMD001A 100 Gbit/s   | mst001a-rt06, rmd001a-rt11, ens002a-rt07               | Greenfield Observatory, GFO  | Maastricht, Roermond, Enschede |
| gen-2723             | NWL SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt03                                           | Northwind Labs, NWL          | Arnhem |
| gen-2724             | SLA SP UNTAGGED UTR002A 100 Gbit/s             | utr002a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-2727             | NWL LP ALM001A-ENS001A 1 Gbit/s                | alm001a-rt02, ens001a-rt11                             | Northwind Labs, NWL          | Almere, Enschede |
| gen-2728             | BFU LP ENS001A-MST002A 1 Gbit/s                | ens001a-rt08, mst002a-rt02                             | Bluefin University, BFU      | Enschede, Maastricht |
| gen-2729             | RWL L2VPN AMS002A-ARN001A-MST001A 10 Gbit/s    | ams002a-rt12, mst001a-rt07, arn001a-rt12               | Redwood Libraries, RWL       | Amsterdam, Maastricht, Arnhem |
| gen-2730             | BFH IP ALM001A 1 Gbit/s                        | alm001a-rt04                                           | Bluefin Hospital, BFH        | Almere |
| gen-2737             | SLA L2VPN ARN001A-MST001A 100 Gbit/s           | mst001a-rt07, arn001a-rt09                             | Silverline Archives, SLA     | Maastricht, Arnhem |
| gen-2738             | SLM IP ARN001A 100 Gbit/s                      | arn001a-rt05                                           | Silverline Museum, SLM       | Arnhem |
| gen-2739             | SLA LP AMS002A-GRQ001A 10 Gbit/s               | grq001a-rt01, ams002a-rt06                             | Silverline Archives, SLA     | Groningen, Amsterdam |
| gen-2741             | GFC IP UTR001A 100 Gbit/s                      | utr001a-rt12                                           | Greenfield College, GFC      | Utrecht |
| gen-2744             | NWL LP ASV002A-RMD002A 100 Gbit/s              | asv002a-rt08, rmd002a-rt09                             | Northwind Labs, NWL          | Amstelveen, Roermond |
| gen-2745             | GFO LP ARN002A-UTR001A 100 Gbit/s              | arn002a-rt04, utr001a-rt08                             | Greenfield Observatory, GFO  | Arnhem, Utrecht |
| gen-2747             | RWI IP ENS001A 100 Gbit/s                      | ens001a-rt04                                           | Redwood Institute, RWI       | Enschede |
| gen-2749             | SLM IP ALM001A 100 Gbit/s                      | alm001a-rt05                                           | Silverline Museum, SLM       | Almere |
| gen-2752             | RWL LP ARN001A-ARN001A 100 Gbit/s              | arn001a-rt02, arn001a-rt01                             | Redwood Libraries, RWL       | Arnhem |
| gen-2753             | GFO SP TAGGED GOR002A 100 Gbit/s               | gor002a-rt06                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-2754             | NWR IP GRQ001A 10 Gbit/s                       | grq001a-rt04                                           | Northwind Research, NWR      | Groningen |
| gen-2755             | BFH SP TAGGED ALM002A 100 Gbit/s               | alm002a-rt10                                           | Bluefin Hospital, BFH        | Almere |
| gen-2756             | RWI IP EHV002A 10 Gbit/s                       | ehv002a-rt12                                           | Redwood Institute, RWI       | Eindhoven |
| gen-2757             | GFC IP ENS001A 100 Gbit/s                      | ens001a-rt08                                           | Greenfield College, GFC      | Enschede |
| gen-2759             | BFU LP GRQ002A-UTR001A 100 Gbit/s              | utr001a-rt12, grq002a-rt05                             | Bluefin University, BFU      | Utrecht, Groningen |
| gen-2761             | GFO L2VPN ARN001A-GRQ001A-UTR001A 100 Gbit/s   | utr002a-rt10, arn001a-rt01, utr001a-rt08, grq001a-rt03 | Greenfield Observatory, GFO  | Utrecht, Arnhem, Groningen |
| gen-2762             | GFC LP RTD001A-UTR002A 100 Gbit/s              | utr002a-rt09, rtd001a-rt02                             | Greenfield College, GFC      | Utrecht, Rotterdam |
| gen-2764             | RWI SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt06                                           | Redwood Institute, RWI       | Almere |
| gen-2770             | NWR IP ARN002A 10 Gbit/s                       | arn002a-rt10                                           | Northwind Research, NWR      | Arnhem |
| gen-2774             | NWL L2VPN ALM002A-GOR002A-RMD002A 1 Gbit/s     | rmd002a-rt09, gor002a-rt04, alm002a-rt09               | Northwind Labs, NWL          | Roermond, Gorinchem, Almere |
| gen-2775             | GFC LP AMS001A-MST001A 1 Gbit/s                | mst001a-rt06, ams001a-rt05                             | Greenfield College, GFC      | Maastricht, Amsterdam |
| gen-2776             | NWR IP MST001A 10 Gbit/s                       | mst001a-rt04                                           | Northwind Research, NWR      | Maastricht |
| gen-2777             | SLA IP AMS002A 100 Gbit/s                      | ams002a-rt03                                           | Silverline Archives, SLA     | Amsterdam |
| gen-2779             | RWI LP EHV001A-GRQ001A 1 Gbit/s                | grq001a-rt09, ehv001a-rt04                             | Redwood Institute, RWI       | Groningen, Eindhoven |
| gen-2780             | RWI L2VPN ALM001A-EHV001A 1 Gbit/s             | ehv001a-rt04, alm001a-rt11                             | Redwood Institute, RWI       | Eindhoven, Almere |
| gen-2785             | RWI IP MST002A 100 Gbit/s                      | mst002a-rt03                                           | Redwood Institute, RWI       | Maastricht |
| gen-2790             | NWR IP RMD001A 100 Gbit/s                      | rmd001a-rt05                                           | Northwind Research, NWR      | Roermond |
| gen-2796             | SLM IP AMS001A 1 Gbit/s                        | ams001a-rt08                                           | Silverline Museum, SLM       | Amsterdam |
| gen-2799             | SLA SP UNTAGGED AMS002A 100 Gbit/s             | ams002a-rt12                                           | Silverline Archives, SLA     | Amsterdam |
| gen-2801             | GFO LP ASV001A-RTD002A 1 Gbit/s                | rtd002a-rt09, asv001a-rt02                             | Greenfield Observatory, GFO  | Rotterdam, Amstelveen |
| gen-2802             | NWR IP GRQ001A 1 Gbit/s                        | grq001a-rt08                                           | Northwind Research, NWR      | Groningen |
| gen-2804             | GFC L2VPN ASV001A-ASV002A-RMD001A 10 Gbit/s    | rmd001a-rt02, asv001a-rt05, utr002a-rt09, asv002a-rt06 | Greenfield College, GFC      | Roermond, Amstelveen, Utrecht |
| gen-2805             | BFU IP RMD002A 1 Gbit/s                        | rmd002a-rt07                                           | Bluefin University, BFU      | Roermond |
| gen-2806             | GFO IP AMS002A 1 Gbit/s                        | ams002a-rt01                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2807             | NWR L2VPN ALM002A-ASV002A-GOR002A 100 Gbit/s   | gor002a-rt05, asv002a-rt04, alm002a-rt09               | Northwind Research, NWR      | Gorinchem, Amstelveen, Almere |
| gen-2808             | BFH L2VPN EHV001A-ENS001A 10 Gbit/s            | ens001a-rt11, ens001a-rt04, ehv001a-rt04               | Bluefin Hospital, BFH        | Enschede, Eindhoven |
| gen-2809             | NWR SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt11                                           | Northwind Research, NWR      | Groningen |
| gen-2810             | GFC LP MST002A-RTD002A 1 Gbit/s                | rtd002a-rt05, mst002a-rt09                             | Greenfield College, GFC      | Rotterdam, Maastricht |
| gen-2811             | RWI L2VPN AMS002A-GRQ001A 1 Gbit/s             | ams002a-rt05, grq001a-rt05                             | Redwood Institute, RWI       | Amsterdam, Groningen |
| gen-2812             | SLM IP UTR001A 10 Gbit/s                       | utr001a-rt08                                           | Silverline Museum, SLM       | Utrecht |
| gen-2814             | RWL IP RMD001A 10 Gbit/s                       | rmd001a-rt11                                           | Redwood Libraries, RWL       | Roermond |
| gen-2816             | NWL L2VPN ENS001A-ENS002A-MST001A 100 Gbit/s   | mst001a-rt04, rmd002a-rt07, ens002a-rt04, ens001a-rt01 | Northwind Labs, NWL          | Maastricht, Roermond, Enschede |
| gen-2818             | BFH IP ASV001A 100 Gbit/s                      | asv001a-rt11                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-2819             | BFH L2VPN ARN001A-GOR001A 100 Gbit/s           | arn001a-rt03, gor001a-rt09                             | Bluefin Hospital, BFH        | Arnhem, Gorinchem |
| gen-2820             | SLA IP ASV002A 1 Gbit/s                        | asv002a-rt03                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2822             | BFH SP TAGGED GOR001A 100 Gbit/s               | gor001a-rt03                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-2825             | RWI SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt10                                           | Redwood Institute, RWI       | Eindhoven |
| gen-2826             | BFH SP UNTAGGED ASV002A 10 Gbit/s              | asv002a-rt04                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-2827             | NWL LP ARN001A-ARN001A 1 Gbit/s                | arn001a-rt12, arn001a-rt02                             | Northwind Labs, NWL          | Arnhem |
| gen-2829             | RWL IP EHV001A 10 Gbit/s                       | ehv001a-rt02                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-2832             | SLA LP ASV002A-MST002A 10 Gbit/s               | mst002a-rt08, asv002a-rt01                             | Silverline Archives, SLA     | Maastricht, Amstelveen |
| gen-2833             | NWR LP ARN002A-GOR002A 10 Gbit/s               | gor002a-rt04, arn002a-rt12                             | Northwind Research, NWR      | Gorinchem, Arnhem |
| gen-2836             | GFC IP ARN002A 1 Gbit/s                        | arn002a-rt10                                           | Greenfield College, GFC      | Arnhem |
| gen-2837             | RWI IP RTD002A 1 Gbit/s                        | rtd002a-rt03                                           | Redwood Institute, RWI       | Rotterdam |
| gen-2840             | SLA SP TAGGED GRQ001A 1 Gbit/s                 | grq001a-rt06                                           | Silverline Archives, SLA     | Groningen |
| gen-2841             | RWL L2VPN EHV001A-MST002A 10 Gbit/s            | mst002a-rt07, ehv001a-rt07                             | Redwood Libraries, RWL       | Maastricht, Eindhoven |
| gen-2843             | NWL SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt07                                           | Northwind Labs, NWL          | Groningen |
| gen-2844             | RWL SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt05                                           | Redwood Libraries, RWL       | Roermond |
| gen-2846             | NWR LP ARN001A-RMD001A 1 Gbit/s                | arn001a-rt01, rmd001a-rt11                             | Northwind Research, NWR      | Arnhem, Roermond |
| gen-2847             | RWL LP RTD002A-UTR001A 1 Gbit/s                | utr001a-rt08, rtd002a-rt09                             | Redwood Libraries, RWL       | Utrecht, Rotterdam |
| gen-2848             | SLA LP ALM002A-AMS002A 100 Gbit/s              | ams002a-rt05, alm002a-rt01                             | Silverline Archives, SLA     | Amsterdam, Almere |
| gen-2850             | NWL SP TAGGED ALM002A 10 Gbit/s                | alm002a-rt03                                           | Northwind Labs, NWL          | Almere |
| gen-2852             | NWR LP ENS002A-RMD001A 10 Gbit/s               | rmd001a-rt12, ens002a-rt06                             | Northwind Research, NWR      | Roermond, Enschede |
| gen-2853             | NWL IP EHV002A 1 Gbit/s                        | ehv002a-rt03                                           | Northwind Labs, NWL          | Eindhoven |
| gen-2854             | BFH IP ASV001A 1 Gbit/s                        | asv001a-rt08                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-2856             | GFC LP AMS001A-RTD002A 1 Gbit/s                | rtd002a-rt08, ams001a-rt04                             | Greenfield College, GFC      | Rotterdam, Amsterdam |
| gen-2857             | GFO IP GOR001A 100 Gbit/s                      | gor001a-rt12                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-2858             | NWR L2VPN RMD001A-RMD002A 1 Gbit/s             | rmd001a-rt12, rmd002a-rt03                             | Northwind Research, NWR      | Roermond |
| gen-2860             | RWI L2VPN ALM002A-AMS001A-AMS002A 1 Gbit/s     | ams002a-rt06, ams001a-rt06, grq002a-rt07, alm002a-rt04 | Redwood Institute, RWI       | Amsterdam, Groningen, Almere |
| gen-2861             | GFO L2VPN ENS002A-RTD002A-UTR002A 10 Gbit/s    | rtd002a-rt09, utr002a-rt06, ens002a-rt08               | Greenfield Observatory, GFO  | Rotterdam, Utrecht, Enschede |
| gen-2863             | RWL LP AMS001A-MST001A 1 Gbit/s                | ams001a-rt02, mst001a-rt10                             | Redwood Libraries, RWL       | Amsterdam, Maastricht |
| gen-2864             | BFH IP EHV001A 10 Gbit/s                       | ehv001a-rt12                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2865             | BFH L2VPN GRQ002A-UTR002A 1 Gbit/s             | grq002a-rt02, utr002a-rt03                             | Bluefin Hospital, BFH        | Groningen, Utrecht |
| gen-2868             | RWI LP GOR001A-GRQ002A 100 Gbit/s              | gor001a-rt12, grq002a-rt09                             | Redwood Institute, RWI       | Gorinchem, Groningen |
| gen-2869             | RWI SP TAGGED MST001A 1 Gbit/s                 | mst001a-rt12                                           | Redwood Institute, RWI       | Maastricht |
| gen-2870             | SLM SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt10                                           | Silverline Museum, SLM       | Amsterdam |
| gen-2873             | RWL IP MST001A 1 Gbit/s                        | mst001a-rt10                                           | Redwood Libraries, RWL       | Maastricht |
| gen-2874             | NWR SP TAGGED EHV002A 10 Gbit/s                | ehv002a-rt06                                           | Northwind Research, NWR      | Eindhoven |
| gen-2875             | SLA L2VPN ASV001A-ASV002A-GOR002A 100 Gbit/s   | asv001a-rt07, mst001a-rt06, asv002a-rt10, gor002a-rt06 | Silverline Archives, SLA     | Amstelveen, Maastricht, Gorinchem |
| gen-2876             | SLA IP ASV001A 1 Gbit/s                        | asv001a-rt05                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2877             | NWL LP EHV001A-GRQ001A 10 Gbit/s               | ehv001a-rt02, grq001a-rt06                             | Northwind Labs, NWL          | Eindhoven, Groningen |
| gen-2878             | BFU LP GOR002A-UTR001A 1 Gbit/s                | gor002a-rt01, utr001a-rt07                             | Bluefin University, BFU      | Gorinchem, Utrecht |
| gen-2879             | RWL LP ALM001A-ALM002A 10 Gbit/s               | alm002a-rt11, alm001a-rt01                             | Redwood Libraries, RWL       | Almere |
| gen-2882             | SLA LP ARN001A-MST001A 1 Gbit/s                | mst001a-rt11, arn001a-rt06                             | Silverline Archives, SLA     | Maastricht, Arnhem |
| gen-2884             | SLM L2VPN ARN001A-GOR002A 100 Gbit/s           | gor002a-rt02, arn001a-rt04                             | Silverline Museum, SLM       | Gorinchem, Arnhem |
| gen-2885             | NWL LP EHV002A-GOR002A 1 Gbit/s                | gor002a-rt01, ehv002a-rt07                             | Northwind Labs, NWL          | Gorinchem, Eindhoven |
| gen-2886             | SLA LP ASV002A-GRQ001A 100 Gbit/s              | grq001a-rt12, asv002a-rt03                             | Silverline Archives, SLA     | Groningen, Amstelveen |
| gen-2887             | RWI SP UNTAGGED RMD002A 1 Gbit/s               | rmd002a-rt03                                           | Redwood Institute, RWI       | Roermond |
| gen-2888             | BFU LP ALM001A-ENS001A 10 Gbit/s               | ens001a-rt06, alm001a-rt06                             | Bluefin University, BFU      | Enschede, Almere |
| gen-2889             | GFO SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt07                                           | Greenfield Observatory, GFO  | Roermond |
| gen-2891             | SLA SP UNTAGGED UTR001A 1 Gbit/s               | utr001a-rt03                                           | Silverline Archives, SLA     | Utrecht |
| gen-2892             | BFU SP UNTAGGED RMD002A 1 Gbit/s               | rmd002a-rt04                                           | Bluefin University, BFU      | Roermond |
| gen-2894             | BFU LP EHV002A-GOR001A 1 Gbit/s                | ehv002a-rt11, gor001a-rt05                             | Bluefin University, BFU      | Eindhoven, Gorinchem |
| gen-2896             | BFU SP UNTAGGED ENS001A 10 Gbit/s              | ens001a-rt01                                           | Bluefin University, BFU      | Enschede |
| gen-2899             | SLA LP GOR002A-MST001A 10 Gbit/s               | mst001a-rt02, gor002a-rt04                             | Silverline Archives, SLA     | Maastricht, Gorinchem |
| gen-2900             | RWI IP RMD001A 1 Gbit/s                        | rmd001a-rt03                                           | Redwood Institute, RWI       | Roermond |
| gen-2901             | BFU SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt01                                           | Bluefin University, BFU      | Roermond |
| gen-2903             | GFO IP AMS002A 100 Gbit/s                      | ams002a-rt01                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2905             | GFO SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt11                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2908             | GFO IP ALM001A 10 Gbit/s                       | alm001a-rt11                                           | Greenfield Observatory, GFO  | Almere |
| gen-2909             | SLM IP ASV001A 1 Gbit/s                        | asv001a-rt06                                           | Silverline Museum, SLM       | Amstelveen |
| gen-2910             | BFU IP ENS002A 100 Gbit/s                      | ens002a-rt11                                           | Bluefin University, BFU      | Enschede |
| gen-2911             | RWL IP UTR002A 1 Gbit/s                        | utr002a-rt07                                           | Redwood Libraries, RWL       | Utrecht |
| gen-2914             | RWL LP AMS002A-EHV002A 10 Gbit/s               | ams002a-rt10, ehv002a-rt06                             | Redwood Libraries, RWL       | Amsterdam, Eindhoven |
| gen-2917             | BFH IP RTD002A 10 Gbit/s                       | rtd002a-rt05                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-2918             | BFH LP ALM002A-GOR001A 100 Gbit/s              | gor001a-rt09, alm002a-rt01                             | Bluefin Hospital, BFH        | Gorinchem, Almere |
| gen-2919             | RWI L2VPN GRQ001A-GRQ002A 100 Gbit/s           | grq001a-rt01, grq002a-rt10                             | Redwood Institute, RWI       | Groningen |
| gen-2920             | RWL L2VPN RTD002A-UTR001A 1 Gbit/s             | rtd002a-rt01, utr001a-rt10                             | Redwood Libraries, RWL       | Rotterdam, Utrecht |
| gen-2921             | GFC LP ARN001A-RMD002A 10 Gbit/s               | arn001a-rt08, rmd002a-rt11                             | Greenfield College, GFC      | Arnhem, Roermond |
| gen-2923             | BFH L2VPN ASV001A-ENS001A-UTR001A 100 Gbit/s   | asv001a-rt11, utr001a-rt01, ens001a-rt09               | Bluefin Hospital, BFH        | Amstelveen, Utrecht, Enschede |
| gen-2924             | NWL LP ARN001A-ARN002A 1 Gbit/s                | arn002a-rt05, arn001a-rt08                             | Northwind Labs, NWL          | Arnhem |
| gen-2926             | SLA IP AMS002A 10 Gbit/s                       | ams002a-rt06                                           | Silverline Archives, SLA     | Amsterdam |
| gen-2927             | RWL L2VPN ENS001A-MST001A-RTD001A 100 Gbit/s   | rtd001a-rt12, mst001a-rt12, ens001a-rt01               | Redwood Libraries, RWL       | Rotterdam, Maastricht, Enschede |
| gen-2928             | BFU L2VPN ARN002A-ENS001A-MST002A 10 Gbit/s    | utr001a-rt01, arn002a-rt05, ens001a-rt10, mst002a-rt08 | Bluefin University, BFU      | Utrecht, Arnhem, Enschede, Maastricht |
| gen-2931             | GFC LP GOR001A-GRQ001A 1 Gbit/s                | grq001a-rt11, gor001a-rt01                             | Greenfield College, GFC      | Groningen, Gorinchem |
| gen-2932             | BFH IP RMD001A 1 Gbit/s                        | rmd001a-rt12                                           | Bluefin Hospital, BFH        | Roermond |
| gen-2934             | BFU IP ALM002A 100 Gbit/s                      | alm002a-rt07                                           | Bluefin University, BFU      | Almere |
| gen-2935             | BFH SP TAGGED ASV002A 10 Gbit/s                | asv002a-rt06                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-2938             | SLM IP ARN001A 10 Gbit/s                       | arn001a-rt01                                           | Silverline Museum, SLM       | Arnhem |
| gen-2939             | GFO L2VPN ARN002A-ASV001A 1 Gbit/s             | arn002a-rt04, asv001a-rt06                             | Greenfield Observatory, GFO  | Arnhem, Amstelveen |
| gen-2940             | RWL IP GOR001A 1 Gbit/s                        | gor001a-rt06                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-2941             | SLM SP UNTAGGED AMS001A 100 Gbit/s             | ams001a-rt02                                           | Silverline Museum, SLM       | Amsterdam |
| gen-2942             | RWL IP EHV002A 10 Gbit/s                       | ehv002a-rt09                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-2946             | SLA IP GRQ001A 100 Gbit/s                      | grq001a-rt10                                           | Silverline Archives, SLA     | Groningen |
| gen-2953             | BFH L2VPN GOR001A-RMD001A 100 Gbit/s           | rmd001a-rt05, gor001a-rt02                             | Bluefin Hospital, BFH        | Roermond, Gorinchem |
| gen-2954             | GFC SP TAGGED GRQ001A 1 Gbit/s                 | grq001a-rt06                                           | Greenfield College, GFC      | Groningen |
| gen-2957             | BFH L2VPN GRQ002A-MST002A-UTR002A 100 Gbit/s   | utr002a-rt04, grq002a-rt01, mst002a-rt07               | Bluefin Hospital, BFH        | Utrecht, Groningen, Maastricht |
| gen-2958             | GFC IP GOR001A 10 Gbit/s                       | gor001a-rt06                                           | Greenfield College, GFC      | Gorinchem |
| gen-2960             | GFO LP ASV001A-EHV001A 100 Gbit/s              | asv001a-rt04, ehv001a-rt06                             | Greenfield Observatory, GFO  | Amstelveen, Eindhoven |
| gen-2961             | SLA L2VPN ALM001A-GRQ002A-MST001A 100 Gbit/s   | alm001a-rt02, grq002a-rt02, mst001a-rt04               | Silverline Archives, SLA     | Almere, Groningen, Maastricht |
| gen-2963             | BFH IP EHV002A 1 Gbit/s                        | ehv002a-rt01                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-2964             | GFC SP TAGGED RTD002A 100 Gbit/s               | rtd002a-rt11                                           | Greenfield College, GFC      | Rotterdam |
| gen-2966             | GFO SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt07                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-2968             | GFC L2VPN ALM002A-GOR001A-MST002A 100 Gbit/s   | mst002a-rt07, mst002a-rt08, alm002a-rt08, gor001a-rt09 | Greenfield College, GFC      | Maastricht, Almere, Gorinchem |
| gen-2969             | RWI IP AMS001A 100 Gbit/s                      | ams001a-rt06                                           | Redwood Institute, RWI       | Amsterdam |
| gen-2970             | GFO SP TAGGED AMS002A 10 Gbit/s                | ams002a-rt06                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-2971             | NWL LP ARN001A-ENS001A 100 Gbit/s              | arn001a-rt11, ens001a-rt09                             | Northwind Labs, NWL          | Arnhem, Enschede |
| gen-2972             | RWI SP UNTAGGED RMD001A 10 Gbit/s              | rmd001a-rt04                                           | Redwood Institute, RWI       | Roermond |
| gen-2974             | BFU L2VPN ARN001A-EHV002A 10 Gbit/s            | ehv002a-rt11, arn001a-rt11                             | Bluefin University, BFU      | Eindhoven, Arnhem |
| gen-2975             | RWL IP ALM001A 10 Gbit/s                       | alm001a-rt05                                           | Redwood Libraries, RWL       | Almere |
| gen-2977             | SLM LP ALM001A-ASV001A 10 Gbit/s               | alm001a-rt01, asv001a-rt07                             | Silverline Museum, SLM       | Almere, Amstelveen |
| gen-2979             | SLA IP ASV001A 10 Gbit/s                       | asv001a-rt04                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2980             | GFO L2VPN ALM002A-GOR002A-UTR002A 10 Gbit/s    | alm002a-rt11, utr002a-rt09, gor002a-rt03               | Greenfield Observatory, GFO  | Almere, Utrecht, Gorinchem |
| gen-2981             | SLM L2VPN MST001A-MST002A-UTR001A 10 Gbit/s    | mst002a-rt09, utr001a-rt06, mst001a-rt06               | Silverline Museum, SLM       | Maastricht, Utrecht |
| gen-2982             | SLA LP ALM002A-GRQ001A 10 Gbit/s               | grq001a-rt09, alm002a-rt05                             | Silverline Archives, SLA     | Groningen, Almere |
| gen-2984             | BFH LP ASV001A-GRQ001A 100 Gbit/s              | grq001a-rt01, asv001a-rt11                             | Bluefin Hospital, BFH        | Groningen, Amstelveen |
| gen-2987             | BFU IP RTD001A 100 Gbit/s                      | rtd001a-rt03                                           | Bluefin University, BFU      | Rotterdam |
| gen-2988             | SLA IP GRQ002A 1 Gbit/s                        | grq002a-rt05                                           | Silverline Archives, SLA     | Groningen |
| gen-2989             | RWI L2VPN ARN002A-RMD001A-UTR002A 1 Gbit/s     | arn002a-rt08, rmd001a-rt09, utr002a-rt06               | Redwood Institute, RWI       | Arnhem, Roermond, Utrecht |
| gen-2990             | BFH LP MST002A-RTD002A 10 Gbit/s               | rtd002a-rt10, mst002a-rt07                             | Bluefin Hospital, BFH        | Rotterdam, Maastricht |
| gen-2992             | RWI LP EHV002A-UTR001A 100 Gbit/s              | ehv002a-rt11, utr001a-rt06                             | Redwood Institute, RWI       | Eindhoven, Utrecht |
| gen-2994             | BFH IP RMD001A 100 Gbit/s                      | rmd001a-rt08                                           | Bluefin Hospital, BFH        | Roermond |
| gen-2995             | SLA IP ASV001A 1 Gbit/s                        | asv001a-rt05                                           | Silverline Archives, SLA     | Amstelveen |
| gen-2996             | GFO LP GRQ002A-GRQ002A 10 Gbit/s               | grq002a-rt03, grq002a-rt11                             | Greenfield Observatory, GFO  | Groningen |
| gen-2997             | BFH IP MST001A 1 Gbit/s                        | mst001a-rt12                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-3001             | SLM LP ASV002A-GRQ001A 1 Gbit/s                | asv002a-rt04, grq001a-rt01                             | Silverline Museum, SLM       | Amstelveen, Groningen |
| gen-3002             | GFC SP UNTAGGED MST002A 100 Gbit/s             | mst002a-rt07                                           | Greenfield College, GFC      | Maastricht |
| gen-3004             | RWL L2VPN MST001A-RMD001A-RTD002A 10 Gbit/s    | rtd002a-rt09, rmd001a-rt05, mst001a-rt03               | Redwood Libraries, RWL       | Rotterdam, Roermond, Maastricht |
| gen-3007             | NWR LP ALM002A-ARN001A 1 Gbit/s                | alm002a-rt03, arn001a-rt11                             | Northwind Research, NWR      | Almere, Arnhem |
| gen-3008             | SLM IP GOR002A 10 Gbit/s                       | gor002a-rt11                                           | Silverline Museum, SLM       | Gorinchem |
| gen-3010             | SLM IP AMS002A 10 Gbit/s                       | ams002a-rt01                                           | Silverline Museum, SLM       | Amsterdam |
| gen-3015             | BFU SP TAGGED RTD002A 1 Gbit/s                 | rtd002a-rt11                                           | Bluefin University, BFU      | Rotterdam |
| gen-3017             | RWL SP UNTAGGED RTD002A 10 Gbit/s              | rtd002a-rt10                                           | Redwood Libraries, RWL       | Rotterdam |
| gen-3019             | RWI SP TAGGED ENS001A 1 Gbit/s                 | ens001a-rt10                                           | Redwood Institute, RWI       | Enschede |
| gen-3024             | GFO IP MST002A 1 Gbit/s                        | mst002a-rt03                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-3025             | GFO SP TAGGED ASV002A 1 Gbit/s                 | asv002a-rt04                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-3027             | SLA IP GOR001A 100 Gbit/s                      | gor001a-rt08                                           | Silverline Archives, SLA     | Gorinchem |
| gen-3031             | GFC LP RTD001A-RTD002A 1 Gbit/s                | rtd002a-rt02, rtd001a-rt03                             | Greenfield College, GFC      | Rotterdam |
| gen-3033             | NWR L2VPN ALM002A-GRQ001A 100 Gbit/s           | alm002a-rt12, grq001a-rt07                             | Northwind Research, NWR      | Almere, Groningen |
| gen-3034             | RWL L2VPN AMS002A-GOR002A-GRQ002A 10 Gbit/s    | ams002a-rt07, grq002a-rt04, gor002a-rt07               | Redwood Libraries, RWL       | Amsterdam, Groningen, Gorinchem |
| gen-3038             | GFC IP ASV001A 100 Gbit/s                      | asv001a-rt03                                           | Greenfield College, GFC      | Amstelveen |
| gen-3039             | GFO LP RMD001A-UTR002A 1 Gbit/s                | utr002a-rt04, rmd001a-rt03                             | Greenfield Observatory, GFO  | Utrecht, Roermond |
| gen-3042             | NWR SP TAGGED RMD002A 1 Gbit/s                 | rmd002a-rt11                                           | Northwind Research, NWR      | Roermond |
| gen-3048             | NWL L2VPN ALM001A-ALM002A-MST001A 10 Gbit/s    | alm001a-rt01, mst001a-rt01, alm002a-rt02               | Northwind Labs, NWL          | Almere, Maastricht |
| gen-3049             | NWL IP ARN002A 10 Gbit/s                       | arn002a-rt10                                           | Northwind Labs, NWL          | Arnhem |
| gen-3051             | BFH L2VPN ASV002A-EHV001A-EHV002A 10 Gbit/s    | asv002a-rt05, ehv002a-rt06, ehv001a-rt10               | Bluefin Hospital, BFH        | Amstelveen, Eindhoven |
| gen-3053             | RWL LP ALM002A-GRQ002A 1 Gbit/s                | grq002a-rt07, alm002a-rt12                             | Redwood Libraries, RWL       | Groningen, Almere |
| gen-3055             | BFU LP GOR001A-MST002A 1 Gbit/s                | mst002a-rt08, gor001a-rt10                             | Bluefin University, BFU      | Maastricht, Gorinchem |
| gen-3056             | RWI IP UTR001A 100 Gbit/s                      | utr001a-rt01                                           | Redwood Institute, RWI       | Utrecht |
| gen-3057             | BFU LP ALM001A-ENS002A 1 Gbit/s                | ens002a-rt12, alm001a-rt12                             | Bluefin University, BFU      | Enschede, Almere |
| gen-3059             | NWL SP TAGGED ASV002A 1 Gbit/s                 | asv002a-rt05                                           | Northwind Labs, NWL          | Amstelveen |
| gen-3060             | NWL SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt11                                           | Northwind Labs, NWL          | Amstelveen |
| gen-3061             | SLA SP UNTAGGED UTR001A 10 Gbit/s              | utr001a-rt01                                           | Silverline Archives, SLA     | Utrecht |
| gen-3062             | BFH LP ASV001A-UTR002A 1 Gbit/s                | asv001a-rt11, utr002a-rt02                             | Bluefin Hospital, BFH        | Amstelveen, Utrecht |
| gen-3066             | RWL L2VPN ALM001A-EHV001A-ENS002A 10 Gbit/s    | alm001a-rt03, alm001a-rt02, ens002a-rt12, ehv001a-rt12 | Redwood Libraries, RWL       | Almere, Enschede, Eindhoven |
| gen-3067             | GFC LP AMS002A-UTR001A 100 Gbit/s              | utr001a-rt11, ams002a-rt03                             | Greenfield College, GFC      | Utrecht, Amsterdam |
| gen-3070             | RWL LP EHV002A-GOR002A 10 Gbit/s               | gor002a-rt11, ehv002a-rt06                             | Redwood Libraries, RWL       | Gorinchem, Eindhoven |
| gen-3072             | GFO LP ARN001A-ASV001A 100 Gbit/s              | asv001a-rt06, arn001a-rt02                             | Greenfield Observatory, GFO  | Amstelveen, Arnhem |
| gen-3073             | RWI IP AMS002A 1 Gbit/s                        | ams002a-rt03                                           | Redwood Institute, RWI       | Amsterdam |
| gen-3077             | GFO SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt05                                           | Greenfield Observatory, GFO  | Enschede |
| gen-3079             | GFO LP GOR002A-GRQ002A 10 Gbit/s               | grq002a-rt08, gor002a-rt05                             | Greenfield Observatory, GFO  | Groningen, Gorinchem |
| gen-3080             | GFO SP UNTAGGED ENS002A 10 Gbit/s              | ens002a-rt12                                           | Greenfield Observatory, GFO  | Enschede |
| gen-3082             | RWL SP TAGGED UTR001A 1 Gbit/s                 | utr001a-rt05                                           | Redwood Libraries, RWL       | Utrecht |
| gen-3083             | GFO IP ASV002A 10 Gbit/s                       | asv002a-rt05                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-3084             | BFU IP EHV002A 1 Gbit/s                        | ehv002a-rt02                                           | Bluefin University, BFU      | Eindhoven |
| gen-3089             | RWL SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt11                                           | Redwood Libraries, RWL       | Almere |
| gen-3092             | NWL SP TAGGED GRQ002A 1 Gbit/s                 | grq002a-rt06                                           | Northwind Labs, NWL          | Groningen |
| gen-3093             | NWR LP EHV002A-MST001A 1 Gbit/s                | mst001a-rt06, ehv002a-rt12                             | Northwind Research, NWR      | Maastricht, Eindhoven |
| gen-3094             | RWI IP RTD001A 1 Gbit/s                        | rtd001a-rt08                                           | Redwood Institute, RWI       | Rotterdam |
| gen-3095             | GFO SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt08                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-3098             | RWI L2VPN ALM001A-ARN001A-GOR001A 1 Gbit/s     | gor001a-rt06, alm001a-rt02, arn001a-rt01               | Redwood Institute, RWI       | Gorinchem, Almere, Arnhem |
| gen-3099             | GFO LP ENS002A-UTR002A 100 Gbit/s              | utr002a-rt01, ens002a-rt09                             | Greenfield Observatory, GFO  | Utrecht, Enschede |
| gen-3100             | GFC IP EHV002A 10 Gbit/s                       | ehv002a-rt03                                           | Greenfield College, GFC      | Eindhoven |
| gen-3101             | BFH L2VPN ARN001A-RMD002A-RTD002A 10 Gbit/s    | arn001a-rt04, rtd002a-rt01, rmd002a-rt01               | Bluefin Hospital, BFH        | Arnhem, Rotterdam, Roermond |
| gen-3102             | RWL IP ALM002A 100 Gbit/s                      | alm002a-rt02                                           | Redwood Libraries, RWL       | Almere |
| gen-3103             | RWI LP ALM001A-UTR002A 1 Gbit/s                | utr002a-rt06, alm001a-rt01                             | Redwood Institute, RWI       | Utrecht, Almere |
| gen-3104             | RWL IP MST001A 100 Gbit/s                      | mst001a-rt07                                           | Redwood Libraries, RWL       | Maastricht |
| gen-3105             | GFO SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt06                                           | Greenfield Observatory, GFO  | Enschede |
| gen-3106             | RWL L2VPN GRQ002A-MST001A-RMD001A 100 Gbit/s   | mst001a-rt12, grq002a-rt08, rmd001a-rt12               | Redwood Libraries, RWL       | Maastricht, Groningen, Roermond |
| gen-3108             | RWI IP GOR001A 1 Gbit/s                        | gor001a-rt08                                           | Redwood Institute, RWI       | Gorinchem |
| gen-3113             | RWL LP AMS002A-ENS002A 100 Gbit/s              | ams002a-rt04, ens002a-rt08                             | Redwood Libraries, RWL       | Amsterdam, Enschede |
| gen-3114             | GFC L2VPN ASV002A-MST001A-RMD001A 100 Gbit/s   | asv002a-rt11, utr001a-rt06, mst001a-rt02, rmd001a-rt08 | Greenfield College, GFC      | Amstelveen, Utrecht, Maastricht, Roermond |
| gen-3115             | BFH LP ASV002A-RMD001A 1 Gbit/s                | rmd001a-rt03, asv002a-rt11                             | Bluefin Hospital, BFH        | Roermond, Amstelveen |
| gen-3116             | SLM IP AMS002A 10 Gbit/s                       | ams002a-rt08                                           | Silverline Museum, SLM       | Amsterdam |
| gen-3117             | RWL SP UNTAGGED GOR001A 1 Gbit/s               | gor001a-rt06                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-3119             | RWI IP GOR002A 100 Gbit/s                      | gor002a-rt01                                           | Redwood Institute, RWI       | Gorinchem |
| gen-3120             | GFO SP UNTAGGED MST001A 10 Gbit/s              | mst001a-rt11                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-3122             | GFO IP RTD002A 10 Gbit/s                       | rtd002a-rt06                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-3123             | GFO L2VPN GOR002A-MST001A 10 Gbit/s            | gor002a-rt09, mst001a-rt06                             | Greenfield Observatory, GFO  | Gorinchem, Maastricht |
| gen-3124             | RWI LP ARN002A-ARN002A 100 Gbit/s              | arn002a-rt10, arn002a-rt11                             | Redwood Institute, RWI       | Arnhem |
| gen-3126             | SLA IP ASV002A 100 Gbit/s                      | asv002a-rt01                                           | Silverline Archives, SLA     | Amstelveen |
| gen-3127             | BFU SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt07                                           | Bluefin University, BFU      | Gorinchem |
| gen-3129             | RWI LP ALM001A-MST002A 1 Gbit/s                | alm001a-rt11, mst002a-rt11                             | Redwood Institute, RWI       | Almere, Maastricht |
| gen-3131             | BFH L2VPN ALM001A-EHV002A-GRQ002A 10 Gbit/s    | alm001a-rt09, ehv002a-rt07, grq002a-rt03, alm001a-rt04 | Bluefin Hospital, BFH        | Almere, Eindhoven, Groningen |
| gen-3135             | GFO LP MST002A-UTR002A 1 Gbit/s                | utr002a-rt09, mst002a-rt12                             | Greenfield Observatory, GFO  | Utrecht, Maastricht |
| gen-3137             | RWI SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt08                                           | Redwood Institute, RWI       | Eindhoven |
| gen-3139             | NWL IP ALM002A 1 Gbit/s                        | alm002a-rt11                                           | Northwind Labs, NWL          | Almere |
| gen-3141             | GFC L2VPN EHV001A-GOR001A-GOR002A 1 Gbit/s     | ehv001a-rt09, gor001a-rt09, gor002a-rt10               | Greenfield College, GFC      | Eindhoven, Gorinchem |
| gen-3144             | SLM SP TAGGED GRQ001A 10 Gbit/s                | grq001a-rt05                                           | Silverline Museum, SLM       | Groningen |
| gen-3148             | GFO IP MST001A 1 Gbit/s                        | mst001a-rt01                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-3149             | RWL SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt02                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-3151             | GFO LP GOR002A-RTD002A 1 Gbit/s                | gor002a-rt08, rtd002a-rt01                             | Greenfield Observatory, GFO  | Gorinchem, Rotterdam |
| gen-3153             | RWI L2VPN ENS001A-MST002A-RMD001A 100 Gbit/s   | mst002a-rt02, utr001a-rt10, ens001a-rt02, rmd001a-rt12 | Redwood Institute, RWI       | Maastricht, Utrecht, Enschede, Roermond |
| gen-3154             | RWI IP RMD001A 10 Gbit/s                       | rmd001a-rt10                                           | Redwood Institute, RWI       | Roermond |
| gen-3155             | RWL IP ARN002A 1 Gbit/s                        | arn002a-rt09                                           | Redwood Libraries, RWL       | Arnhem |
| gen-3157             | BFH IP ENS002A 1 Gbit/s                        | ens002a-rt05                                           | Bluefin Hospital, BFH        | Enschede |
| gen-3158             | RWI L2VPN AMS001A-RMD002A 1 Gbit/s             | rmd002a-rt05, ams001a-rt06                             | Redwood Institute, RWI       | Roermond, Amsterdam |
| gen-3159             | RWI SP TAGGED GRQ002A 10 Gbit/s                | grq002a-rt10                                           | Redwood Institute, RWI       | Groningen |
| gen-3162             | NWR L2VPN GOR002A-GRQ001A 100 Gbit/s           | gor002a-rt09, grq001a-rt08                             | Northwind Research, NWR      | Gorinchem, Groningen |
| gen-3163             | RWL SP TAGGED GOR001A 10 Gbit/s                | gor001a-rt10                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-3164             | SLA LP ARN001A-GOR002A 1 Gbit/s                | arn001a-rt01, gor002a-rt02                             | Silverline Archives, SLA     | Arnhem, Gorinchem |
| gen-3165             | RWL IP UTR002A 10 Gbit/s                       | utr002a-rt03                                           | Redwood Libraries, RWL       | Utrecht |
| gen-3169             | GFO L2VPN AMS002A-ARN002A-EHV002A 10 Gbit/s    | ehv002a-rt04, gor001a-rt06, arn002a-rt02, ams002a-rt12 | Greenfield Observatory, GFO  | Eindhoven, Gorinchem, Arnhem, Amsterdam |
| gen-3170             | RWI IP ENS002A 10 Gbit/s                       | ens002a-rt12                                           | Redwood Institute, RWI       | Enschede |
| gen-3172             | NWR SP UNTAGGED GOR001A 10 Gbit/s              | gor001a-rt07                                           | Northwind Research, NWR      | Gorinchem |
| gen-3173             | RWL L2VPN ALM002A-EHV001A-GRQ001A 100 Gbit/s   | rmd002a-rt12, ehv001a-rt12, alm002a-rt03, grq001a-rt06 | Redwood Libraries, RWL       | Roermond, Eindhoven, Almere, Groningen |
| gen-3176             | SLA L2VPN ALM001A-ARN002A 1 Gbit/s             | alm001a-rt12, arn002a-rt03                             | Silverline Archives, SLA     | Almere, Arnhem |
| gen-3177             | NWR L2VPN GRQ002A-RMD002A 100 Gbit/s           | grq002a-rt12, rmd002a-rt06                             | Northwind Research, NWR      | Groningen, Roermond |
| gen-3179             | BFH L2VPN GOR002A-GRQ002A-RTD002A 1 Gbit/s     | grq002a-rt06, gor002a-rt08, rtd002a-rt10               | Bluefin Hospital, BFH        | Groningen, Gorinchem, Rotterdam |
| gen-3180             | GFC IP ALM001A 1 Gbit/s                        | alm001a-rt10                                           | Greenfield College, GFC      | Almere |
| gen-3181             | SLA SP TAGGED ALM002A 10 Gbit/s                | alm002a-rt02                                           | Silverline Archives, SLA     | Almere |
| gen-3182             | BFH LP ASV001A-ASV002A 10 Gbit/s               | asv002a-rt02, asv001a-rt08                             | Bluefin Hospital, BFH        | Amstelveen |
| gen-3184             | RWI LP AMS001A-EHV001A 10 Gbit/s               | ehv001a-rt02, ams001a-rt06                             | Redwood Institute, RWI       | Eindhoven, Amsterdam |
| gen-3185             | RWI IP RMD002A 1 Gbit/s                        | rmd002a-rt07                                           | Redwood Institute, RWI       | Roermond |
| gen-3187             | BFH LP GOR001A-MST002A 10 Gbit/s               | mst002a-rt04, gor001a-rt07                             | Bluefin Hospital, BFH        | Maastricht, Gorinchem |
| gen-3188             | RWL LP ALM001A-ARN002A 10 Gbit/s               | alm001a-rt06, arn002a-rt04                             | Redwood Libraries, RWL       | Almere, Arnhem |
| gen-3189             | RWL LP ARN002A-MST001A 1 Gbit/s                | mst001a-rt02, arn002a-rt08                             | Redwood Libraries, RWL       | Maastricht, Arnhem |
| gen-3190             | GFO SP TAGGED UTR002A 1 Gbit/s                 | utr002a-rt11                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-3192             | GFC IP GRQ001A 1 Gbit/s                        | grq001a-rt12                                           | Greenfield College, GFC      | Groningen |
| gen-3193             | SLM L2VPN GRQ002A-UTR001A 100 Gbit/s           | utr001a-rt07, grq002a-rt03                             | Silverline Museum, SLM       | Utrecht, Groningen |
| gen-3194             | NWL SP TAGGED GRQ001A 10 Gbit/s                | grq001a-rt08                                           | Northwind Labs, NWL          | Groningen |
| gen-3196             | NWR SP UNTAGGED ASV002A 10 Gbit/s              | asv002a-rt02                                           | Northwind Research, NWR      | Amstelveen |
| gen-3197             | BFH SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt12                                           | Bluefin Hospital, BFH        | Enschede |
| gen-3201             | NWL SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt11                                           | Northwind Labs, NWL          | Groningen |
| gen-3203             | NWL L2VPN ARN002A-ENS001A-GRQ001A 10 Gbit/s    | ens001a-rt06, grq001a-rt05, arn002a-rt05               | Northwind Labs, NWL          | Enschede, Groningen, Arnhem |
| gen-3204             | RWI IP GRQ002A 10 Gbit/s                       | grq002a-rt12                                           | Redwood Institute, RWI       | Groningen |
| gen-3205             | GFC IP ENS001A 100 Gbit/s                      | ens001a-rt08                                           | Greenfield College, GFC      | Enschede |
| gen-3206             | BFU IP EHV001A 1 Gbit/s                        | ehv001a-rt11                                           | Bluefin University, BFU      | Eindhoven |
| gen-3208             | RWL L2VPN ARN001A-GRQ002A 100 Gbit/s           | arn001a-rt09, grq002a-rt03                             | Redwood Libraries, RWL       | Arnhem, Groningen |
| gen-3209             | NWR IP GOR002A 1 Gbit/s                        | gor002a-rt07                                           | Northwind Research, NWR      | Gorinchem |
| gen-3212             | GFC LP GRQ002A-RMD002A 100 Gbit/s              | grq002a-rt03, rmd002a-rt07                             | Greenfield College, GFC      | Groningen, Roermond |
| gen-3213             | BFH SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt10                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-3214             | BFU IP GOR002A 100 Gbit/s                      | gor002a-rt05                                           | Bluefin University, BFU      | Gorinchem |
| gen-3215             | GFC LP MST002A-MST002A 1 Gbit/s                | mst002a-rt08, mst002a-rt10                             | Greenfield College, GFC      | Maastricht |
| gen-3216             | GFC L2VPN ENS001A-RTD002A 100 Gbit/s           | ens001a-rt08, rtd002a-rt03                             | Greenfield College, GFC      | Enschede, Rotterdam |
| gen-3218             | RWI LP RMD002A-UTR001A 100 Gbit/s              | utr001a-rt06, rmd002a-rt05                             | Redwood Institute, RWI       | Utrecht, Roermond |
| gen-3219             | GFO LP ARN002A-UTR002A 1 Gbit/s                | arn002a-rt01, utr002a-rt05                             | Greenfield Observatory, GFO  | Arnhem, Utrecht |
| gen-3223             | RWL LP MST001A-RTD002A 1 Gbit/s                | rtd002a-rt01, mst001a-rt10                             | Redwood Libraries, RWL       | Rotterdam, Maastricht |
| gen-3225             | BFU SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt08                                           | Bluefin University, BFU      | Arnhem |
| gen-3226             | BFH SP TAGGED ALM002A 100 Gbit/s               | alm002a-rt11                                           | Bluefin Hospital, BFH        | Almere |
| gen-3227             | RWL LP ARN002A-MST001A 1 Gbit/s                | arn002a-rt11, mst001a-rt10                             | Redwood Libraries, RWL       | Arnhem, Maastricht |
| gen-3229             | NWR LP ALM002A-ARN001A 10 Gbit/s               | alm002a-rt03, arn001a-rt03                             | Northwind Research, NWR      | Almere, Arnhem |
| gen-3230             | NWL L2VPN ASV002A-RMD002A 10 Gbit/s            | rmd002a-rt11, asv002a-rt01                             | Northwind Labs, NWL          | Roermond, Amstelveen |
| gen-3231             | SLM SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt11                                           | Silverline Museum, SLM       | Arnhem |
| gen-3232             | GFO IP AMS001A 1 Gbit/s                        | ams001a-rt04                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-3233             | GFO L2VPN ARN001A-ASV001A-RTD001A 1 Gbit/s     | rtd001a-rt09, asv001a-rt09, arn001a-rt12, utr002a-rt10 | Greenfield Observatory, GFO  | Rotterdam, Amstelveen, Arnhem, Utrecht |
| gen-3236             | BFH SP UNTAGGED RTD001A 1 Gbit/s               | rtd001a-rt11                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-3237             | SLA SP TAGGED ASV001A 1 Gbit/s                 | asv001a-rt03                                           | Silverline Archives, SLA     | Amstelveen |
| gen-3238             | GFO SP UNTAGGED ALM002A 100 Gbit/s             | alm002a-rt12                                           | Greenfield Observatory, GFO  | Almere |
| gen-3239             | GFC LP AMS001A-ASV002A 10 Gbit/s               | asv002a-rt03, ams001a-rt09                             | Greenfield College, GFC      | Amstelveen, Amsterdam |
| gen-3240             | BFU SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt06                                           | Bluefin University, BFU      | Almere |
| gen-3241             | BFH IP EHV001A 1 Gbit/s                        | ehv001a-rt10                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-3242             | GFO SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt08                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-3243             | RWI LP RTD001A-RTD002A 10 Gbit/s               | rtd001a-rt03, rtd002a-rt11                             | Redwood Institute, RWI       | Rotterdam |
| gen-3244             | GFO IP GRQ001A 1 Gbit/s                        | grq001a-rt10                                           | Greenfield Observatory, GFO  | Groningen |
| gen-3246             | BFH LP ASV002A-ENS002A 100 Gbit/s              | ens002a-rt12, asv002a-rt05                             | Bluefin Hospital, BFH        | Enschede, Amstelveen |
| gen-3247             | SLM LP ALM001A-GRQ002A 1 Gbit/s                | grq002a-rt01, alm001a-rt09                             | Silverline Museum, SLM       | Groningen, Almere |
| gen-3250             | NWR IP ASV001A 1 Gbit/s                        | asv001a-rt11                                           | Northwind Research, NWR      | Amstelveen |
| gen-3255             | GFC SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt08                                           | Greenfield College, GFC      | Arnhem |
| gen-3256             | GFO SP UNTAGGED AMS001A 1 Gbit/s               | ams001a-rt04                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-3258             | BFH L2VPN ALM001A-ARN001A-GRQ001A 1 Gbit/s     | arn001a-rt04, alm001a-rt11, grq001a-rt10               | Bluefin Hospital, BFH        | Arnhem, Almere, Groningen |
| gen-3260             | GFC L2VPN ASV002A-EHV002A-RTD002A 1 Gbit/s     | asv002a-rt01, ehv002a-rt08, rtd002a-rt09               | Greenfield College, GFC      | Amstelveen, Eindhoven, Rotterdam |
| gen-3261             | NWR SP UNTAGGED ENS001A 10 Gbit/s              | ens001a-rt05                                           | Northwind Research, NWR      | Enschede |
| gen-3263             | RWL LP ARN001A-GOR001A 10 Gbit/s               | gor001a-rt04, arn001a-rt07                             | Redwood Libraries, RWL       | Gorinchem, Arnhem |
| gen-3265             | RWI IP UTR001A 10 Gbit/s                       | utr001a-rt07                                           | Redwood Institute, RWI       | Utrecht |
| gen-3266             | BFU SP TAGGED RMD001A 1 Gbit/s                 | rmd001a-rt03                                           | Bluefin University, BFU      | Roermond |
| gen-3269             | NWL SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt09                                           | Northwind Labs, NWL          | Groningen |
| gen-3273             | RWL SP UNTAGGED MST001A 1 Gbit/s               | mst001a-rt03                                           | Redwood Libraries, RWL       | Maastricht |
| gen-3274             | BFU IP ARN002A 10 Gbit/s                       | arn002a-rt10                                           | Bluefin University, BFU      | Arnhem |
| gen-3275             | BFH SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt05                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-3276             | BFH IP UTR001A 100 Gbit/s                      | utr001a-rt06                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-3277             | GFC IP ASV002A 1 Gbit/s                        | asv002a-rt07                                           | Greenfield College, GFC      | Amstelveen |
| gen-3280             | GFO IP GOR002A 1 Gbit/s                        | gor002a-rt06                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-3281             | SLA LP AMS002A-ASV002A 1 Gbit/s                | asv002a-rt05, ams002a-rt09                             | Silverline Archives, SLA     | Amstelveen, Amsterdam |
| gen-3283             | BFH L2VPN ALM001A-GOR001A 100 Gbit/s           | gor001a-rt02, alm001a-rt01, alm001a-rt12               | Bluefin Hospital, BFH        | Gorinchem, Almere |
| gen-3286             | SLA IP AMS001A 10 Gbit/s                       | ams001a-rt06                                           | Silverline Archives, SLA     | Amsterdam |
| gen-3287             | RWI L2VPN GOR001A-MST001A 10 Gbit/s            | gor001a-rt11, mst001a-rt12                             | Redwood Institute, RWI       | Gorinchem, Maastricht |
| gen-3288             | BFH SP TAGGED ALM002A 10 Gbit/s                | alm002a-rt05                                           | Bluefin Hospital, BFH        | Almere |
| gen-3290             | BFU IP RMD001A 100 Gbit/s                      | rmd001a-rt07                                           | Bluefin University, BFU      | Roermond |
| gen-3292             | RWL L2VPN ARN001A-UTR001A 1 Gbit/s             | arn001a-rt05, utr001a-rt01                             | Redwood Libraries, RWL       | Arnhem, Utrecht |
| gen-3294             | RWI L2VPN ALM001A-AMS002A-ENS002A 1 Gbit/s     | alm001a-rt06, grq001a-rt03, ens002a-rt09, ams002a-rt07 | Redwood Institute, RWI       | Almere, Groningen, Enschede, Amsterdam |
| gen-3296             | NWR SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt10                                           | Northwind Research, NWR      | Arnhem |
| gen-3300             | BFU SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt09                                           | Bluefin University, BFU      | Amstelveen |
| gen-3301             | RWL LP GRQ001A-RTD001A 100 Gbit/s              | rtd001a-rt04, grq001a-rt08                             | Redwood Libraries, RWL       | Rotterdam, Groningen |
| gen-3303             | NWL L2VPN ALM002A-ASV001A-EHV001A 1 Gbit/s     | asv001a-rt12, ehv001a-rt01, gor002a-rt12, alm002a-rt02 | Northwind Labs, NWL          | Amstelveen, Eindhoven, Gorinchem, Almere |
| gen-3304             | SLM LP ALM001A-ASV001A 100 Gbit/s              | asv001a-rt04, alm001a-rt07                             | Silverline Museum, SLM       | Amstelveen, Almere |
| gen-3306             | RWI L2VPN ALM001A-AMS002A 10 Gbit/s            | ams002a-rt02, alm001a-rt06                             | Redwood Institute, RWI       | Amsterdam, Almere |
| gen-3307             | BFU IP ASV002A 100 Gbit/s                      | asv002a-rt04                                           | Bluefin University, BFU      | Amstelveen |
| gen-3308             | SLA LP ARN001A-ARN002A 1 Gbit/s                | arn001a-rt03, arn002a-rt01                             | Silverline Archives, SLA     | Arnhem |
| gen-3309             | RWL SP TAGGED UTR002A 1 Gbit/s                 | utr002a-rt08                                           | Redwood Libraries, RWL       | Utrecht |
| gen-3310             | NWL L2VPN ARN001A-GRQ002A 100 Gbit/s           | arn001a-rt02, grq002a-rt02                             | Northwind Labs, NWL          | Arnhem, Groningen |
| gen-3311             | RWL IP AMS002A 10 Gbit/s                       | ams002a-rt05                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-3312             | NWR SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt10                                           | Northwind Research, NWR      | Amstelveen |
| gen-3314             | GFO IP ASV002A 10 Gbit/s                       | asv002a-rt09                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-3318             | SLA IP ALM001A 100 Gbit/s                      | alm001a-rt09                                           | Silverline Archives, SLA     | Almere |
| gen-3319             | RWL L2VPN GOR002A-RTD001A-RTD002A 100 Gbit/s   | rtd001a-rt05, gor002a-rt07, rtd002a-rt11               | Redwood Libraries, RWL       | Rotterdam, Gorinchem |
| gen-3320             | GFC SP TAGGED MST001A 100 Gbit/s               | mst001a-rt08                                           | Greenfield College, GFC      | Maastricht |
| gen-3322             | RWI IP GRQ002A 100 Gbit/s                      | grq002a-rt07                                           | Redwood Institute, RWI       | Groningen |
| gen-3323             | GFO IP RTD001A 1 Gbit/s                        | rtd001a-rt10                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-3325             | RWI SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt02                                           | Redwood Institute, RWI       | Arnhem |
| gen-3326             | SLM L2VPN ALM002A-GOR002A 10 Gbit/s            | alm002a-rt03, gor002a-rt09                             | Silverline Museum, SLM       | Almere, Gorinchem |
| gen-3328             | GFO IP UTR001A 100 Gbit/s                      | utr001a-rt05                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-3331             | RWL IP UTR001A 1 Gbit/s                        | utr001a-rt11                                           | Redwood Libraries, RWL       | Utrecht |
| gen-3332             | BFU L2VPN ARN002A-ASV001A-RTD001A 1 Gbit/s     | arn002a-rt06, asv001a-rt11, rtd001a-rt10               | Bluefin University, BFU      | Arnhem, Amstelveen, Rotterdam |
| gen-3333             | GFC SP UNTAGGED UTR002A 10 Gbit/s              | utr002a-rt01                                           | Greenfield College, GFC      | Utrecht |
| gen-3334             | RWL IP GRQ002A 1 Gbit/s                        | grq002a-rt12                                           | Redwood Libraries, RWL       | Groningen |
| gen-3335             | SLM IP ARN002A 100 Gbit/s                      | arn002a-rt11                                           | Silverline Museum, SLM       | Arnhem |
| gen-3336             | BFU LP ARN001A-RMD002A 1 Gbit/s                | rmd002a-rt04, arn001a-rt11                             | Bluefin University, BFU      | Roermond, Arnhem |
| gen-3338             | RWL L2VPN ALM002A-EHV001A-GRQ001A 10 Gbit/s    | alm002a-rt11, ehv001a-rt08, grq001a-rt10               | Redwood Libraries, RWL       | Almere, Eindhoven, Groningen |
| gen-3340             | SLM LP AMS002A-UTR002A 100 Gbit/s              | ams002a-rt09, utr002a-rt06                             | Silverline Museum, SLM       | Amsterdam, Utrecht |
| gen-3341             | NWL IP ALM001A 10 Gbit/s                       | alm001a-rt05                                           | Northwind Labs, NWL          | Almere |
| gen-3342             | NWR IP MST002A 100 Gbit/s                      | mst002a-rt08                                           | Northwind Research, NWR      | Maastricht |
| gen-3343             | NWR SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt08                                           | Northwind Research, NWR      | Enschede |
| gen-3346             | SLA IP GOR001A 100 Gbit/s                      | gor001a-rt08                                           | Silverline Archives, SLA     | Gorinchem |
| gen-3347             | RWL L2VPN ENS001A-RMD002A 1 Gbit/s             | ens001a-rt06, rmd002a-rt03                             | Redwood Libraries, RWL       | Enschede, Roermond |
| gen-3349             | BFU SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt12                                           | Bluefin University, BFU      | Eindhoven |
| gen-3352             | GFO IP UTR001A 100 Gbit/s                      | utr001a-rt04                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-3354             | RWI L2VPN RMD001A-RMD002A 10 Gbit/s            | rmd001a-rt09, rmd002a-rt11                             | Redwood Institute, RWI       | Roermond |
| gen-3355             | RWL SP UNTAGGED ARN001A 10 Gbit/s              | arn001a-rt09                                           | Redwood Libraries, RWL       | Arnhem |
| gen-3356             | SLM IP MST001A 1 Gbit/s                        | mst001a-rt03                                           | Silverline Museum, SLM       | Maastricht |
| gen-3359             | BFH L2VPN ARN001A-GOR002A-RMD001A 1 Gbit/s     | rmd001a-rt03, arn001a-rt01, gor002a-rt12, rmd002a-rt04 | Bluefin Hospital, BFH        | Roermond, Arnhem, Gorinchem |
| gen-3360             | NWR SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt10                                           | Northwind Research, NWR      | Almere |
| gen-3361             | GFC IP RMD002A 10 Gbit/s                       | rmd002a-rt05                                           | Greenfield College, GFC      | Roermond |
| gen-3364             | BFH LP MST002A-UTR001A 10 Gbit/s               | mst002a-rt06, utr001a-rt08                             | Bluefin Hospital, BFH        | Maastricht, Utrecht |
| gen-3365             | SLA IP MST002A 100 Gbit/s                      | mst002a-rt10                                           | Silverline Archives, SLA     | Maastricht |
| gen-3366             | BFH L2VPN ARN001A-RTD001A-UTR001A 10 Gbit/s    | utr001a-rt07, arn001a-rt08, rtd001a-rt11, utr002a-rt07 | Bluefin Hospital, BFH        | Utrecht, Arnhem, Rotterdam |
| gen-3367             | BFH IP ARN002A 100 Gbit/s                      | arn002a-rt09                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-3371             | SLM IP AMS002A 100 Gbit/s                      | ams002a-rt05                                           | Silverline Museum, SLM       | Amsterdam |
| gen-3372             | SLA SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt02                                           | Silverline Archives, SLA     | Gorinchem |
| gen-3374             | GFO SP UNTAGGED RTD002A 1 Gbit/s               | rtd002a-rt01                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-3378             | GFC L2VPN ALM001A-EHV002A-MST002A 10 Gbit/s    | ehv002a-rt12, mst002a-rt07, alm001a-rt03               | Greenfield College, GFC      | Eindhoven, Maastricht, Almere |
| gen-3379             | RWI SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt10                                           | Redwood Institute, RWI       | Groningen |
| gen-3381             | GFO L2VPN ASV001A-EHV002A-GOR001A 10 Gbit/s    | ehv002a-rt03, gor001a-rt04, asv001a-rt07, utr001a-rt10 | Greenfield Observatory, GFO  | Eindhoven, Gorinchem, Amstelveen, Utrecht |
| gen-3382             | SLM LP ALM001A-ASV002A 10 Gbit/s               | alm001a-rt04, asv002a-rt12                             | Silverline Museum, SLM       | Almere, Amstelveen |
| gen-3383             | GFC L2VPN ALM001A-AMS001A 1 Gbit/s             | ams001a-rt08, alm001a-rt06, alm001a-rt11               | Greenfield College, GFC      | Amsterdam, Almere |
| gen-3384             | RWI L2VPN EHV002A-RMD002A-RTD002A 1 Gbit/s     | rtd002a-rt11, ehv002a-rt04, rmd002a-rt04               | Redwood Institute, RWI       | Rotterdam, Eindhoven, Roermond |
| gen-3385             | BFU LP UTR001A-UTR002A 10 Gbit/s               | utr001a-rt10, utr002a-rt08                             | Bluefin University, BFU      | Utrecht |
| gen-3386             | BFU LP ARN001A-GRQ001A 10 Gbit/s               | grq001a-rt09, arn001a-rt05                             | Bluefin University, BFU      | Groningen, Arnhem |
| gen-3387             | SLA L2VPN AMS002A-ASV001A-GOR001A 10 Gbit/s    | gor001a-rt04, gor001a-rt03, asv001a-rt07, ams002a-rt07 | Silverline Archives, SLA     | Gorinchem, Amstelveen, Amsterdam |
| gen-3388             | GFO IP ARN001A 10 Gbit/s                       | arn001a-rt03                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-3389             | RWL SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt05                                           | Redwood Libraries, RWL       | Arnhem |
| gen-3391             | GFO L2VPN GRQ001A-GRQ002A 100 Gbit/s           | grq001a-rt01, grq002a-rt03                             | Greenfield Observatory, GFO  | Groningen |
| gen-3393             | SLA SP UNTAGGED ARN002A 100 Gbit/s             | arn002a-rt06                                           | Silverline Archives, SLA     | Arnhem |
| gen-3396             | GFO SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt02                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-3397             | NWR SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt09                                           | Northwind Research, NWR      | Almere |
| gen-3402             | NWL SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt11                                           | Northwind Labs, NWL          | Almere |
| gen-3404             | RWI IP ARN001A 1 Gbit/s                        | arn001a-rt05                                           | Redwood Institute, RWI       | Arnhem |
| gen-3405             | RWI SP UNTAGGED GOR002A 1 Gbit/s               | gor002a-rt04                                           | Redwood Institute, RWI       | Gorinchem |
| gen-3408             | SLA LP AMS002A-ARN001A 1 Gbit/s                | arn001a-rt01, ams002a-rt11                             | Silverline Archives, SLA     | Arnhem, Amsterdam |
| gen-3410             | SLM L2VPN ARN002A-ASV002A 10 Gbit/s            | asv002a-rt10, arn002a-rt10                             | Silverline Museum, SLM       | Amstelveen, Arnhem |
| gen-3411             | SLA SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt11                                           | Silverline Archives, SLA     | Maastricht |
| gen-3413             | BFH L2VPN ASV002A-RTD001A 10 Gbit/s            | asv002a-rt07, rtd001a-rt02, asv002a-rt10               | Bluefin Hospital, BFH        | Amstelveen, Rotterdam |
| gen-3414             | RWI SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt11                                           | Redwood Institute, RWI       | Maastricht |
| gen-3415             | BFU LP ARN002A-GRQ002A 10 Gbit/s               | grq002a-rt05, arn002a-rt09                             | Bluefin University, BFU      | Groningen, Arnhem |
| gen-3417             | SLM IP ALM002A 100 Gbit/s                      | alm002a-rt04                                           | Silverline Museum, SLM       | Almere |
| gen-3418             | NWL SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt05                                           | Northwind Labs, NWL          | Groningen |
| gen-3419             | BFU L2VPN ASV002A-RMD002A 100 Gbit/s           | asv002a-rt10, rmd002a-rt08                             | Bluefin University, BFU      | Amstelveen, Roermond |
| gen-3421             | RWI IP UTR001A 10 Gbit/s                       | utr001a-rt04                                           | Redwood Institute, RWI       | Utrecht |
| gen-3422             | GFO IP RTD001A 10 Gbit/s                       | rtd001a-rt11                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-3423             | BFH LP GOR002A-UTR002A 1 Gbit/s                | utr002a-rt10, gor002a-rt09                             | Bluefin Hospital, BFH        | Utrecht, Gorinchem |
| gen-3424             | BFH LP EHV001A-GOR002A 10 Gbit/s               | gor002a-rt07, ehv001a-rt10                             | Bluefin Hospital, BFH        | Gorinchem, Eindhoven |
| gen-3427             | GFC IP ALM001A 1 Gbit/s                        | alm001a-rt04                                           | Greenfield College, GFC      | Almere |
| gen-3428             | GFO LP ENS002A-RTD002A 1 Gbit/s                | rtd002a-rt04, ens002a-rt03                             | Greenfield Observatory, GFO  | Rotterdam, Enschede |
| gen-3433             | GFO SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt04                                           | Greenfield Observatory, GFO  | Almere |
| gen-3435             | RWL SP UNTAGGED AMS002A 10 Gbit/s              | ams002a-rt11                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-3436             | GFO IP GOR002A 1 Gbit/s                        | gor002a-rt06                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-3439             | NWL LP ENS001A-RMD001A 1 Gbit/s                | ens001a-rt02, rmd001a-rt10                             | Northwind Labs, NWL          | Enschede, Roermond |
| gen-3440             | RWL IP RMD002A 1 Gbit/s                        | rmd002a-rt02                                           | Redwood Libraries, RWL       | Roermond |
| gen-3444             | GFC LP RMD001A-RTD002A 10 Gbit/s               | rmd001a-rt04, rtd002a-rt09                             | Greenfield College, GFC      | Roermond, Rotterdam |
| gen-3445             | NWL LP GRQ002A-MST001A 10 Gbit/s               | mst001a-rt02, grq002a-rt05                             | Northwind Labs, NWL          | Maastricht, Groningen |
| gen-3448             | NWL LP EHV001A-ENS001A 10 Gbit/s               | ehv001a-rt01, ens001a-rt11                             | Northwind Labs, NWL          | Eindhoven, Enschede |
| gen-3449             | RWI L2VPN ENS001A-MST001A-RMD001A 100 Gbit/s   | ens001a-rt10, rmd001a-rt06, mst001a-rt08               | Redwood Institute, RWI       | Enschede, Roermond, Maastricht |
| gen-3450             | SLA SP TAGGED ALM001A 1 Gbit/s                 | alm001a-rt11                                           | Silverline Archives, SLA     | Almere |
| gen-3452             | GFC LP GRQ001A-RTD001A 1 Gbit/s                | rtd001a-rt12, grq001a-rt10                             | Greenfield College, GFC      | Rotterdam, Groningen |
| gen-3454             | BFU LP ARN002A-RTD001A 10 Gbit/s               | rtd001a-rt05, arn002a-rt04                             | Bluefin University, BFU      | Rotterdam, Arnhem |
| gen-3457             | GFC LP ASV002A-RMD001A 10 Gbit/s               | rmd001a-rt05, asv002a-rt05                             | Greenfield College, GFC      | Roermond, Amstelveen |
| gen-3458             | NWR SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt04                                           | Northwind Research, NWR      | Almere |
| gen-3461             | RWL LP ALM001A-ALM002A 1 Gbit/s                | alm002a-rt12, alm001a-rt12                             | Redwood Libraries, RWL       | Almere |
| gen-3463             | RWL SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt12                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-3468             | BFH SP TAGGED EHV001A 10 Gbit/s                | ehv001a-rt09                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-3469             | BFU IP EHV002A 1 Gbit/s                        | ehv002a-rt06                                           | Bluefin University, BFU      | Eindhoven |
| gen-3470             | GFO IP ASV002A 1 Gbit/s                        | asv002a-rt07                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-3471             | NWR SP UNTAGGED RMD002A 1 Gbit/s               | rmd002a-rt07                                           | Northwind Research, NWR      | Roermond |
| gen-3474             | NWR IP EHV002A 1 Gbit/s                        | ehv002a-rt03                                           | Northwind Research, NWR      | Eindhoven |
| gen-3475             | GFO L2VPN AMS002A-ASV001A-GRQ002A 100 Gbit/s   | grq002a-rt01, rtd002a-rt05, ams002a-rt03, asv001a-rt05 | Greenfield Observatory, GFO  | Groningen, Rotterdam, Amsterdam, Amstelveen |
| gen-3479             | NWL LP ARN001A-ARN002A 1 Gbit/s                | arn002a-rt06, arn001a-rt11                             | Northwind Labs, NWL          | Arnhem |
| gen-3481             | NWR IP ASV002A 1 Gbit/s                        | asv002a-rt09                                           | Northwind Research, NWR      | Amstelveen |
| gen-3482             | BFU SP UNTAGGED ASV001A 10 Gbit/s              | asv001a-rt05                                           | Bluefin University, BFU      | Amstelveen |
| gen-3483             | GFC L2VPN AMS001A-AMS002A-RMD001A 1 Gbit/s     | ams001a-rt05, rmd001a-rt09, ams002a-rt04               | Greenfield College, GFC      | Amsterdam, Roermond |
| gen-3484             | GFO SP TAGGED AMS002A 10 Gbit/s                | ams002a-rt07                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-3485             | NWR LP ALM001A-GOR002A 10 Gbit/s               | gor002a-rt09, alm001a-rt01                             | Northwind Research, NWR      | Gorinchem, Almere |
| gen-3488             | BFU IP RMD002A 1 Gbit/s                        | rmd002a-rt12                                           | Bluefin University, BFU      | Roermond |
| gen-3489             | GFO IP AMS002A 1 Gbit/s                        | ams002a-rt08                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-3490             | NWL LP ARN001A-ASV002A 100 Gbit/s              | arn001a-rt09, asv002a-rt09                             | Northwind Labs, NWL          | Arnhem, Amstelveen |
| gen-3492             | BFU SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt01                                           | Bluefin University, BFU      | Eindhoven |
| gen-3493             | BFH IP ENS002A 100 Gbit/s                      | ens002a-rt05                                           | Bluefin Hospital, BFH        | Enschede |
| gen-3494             | RWI SP UNTAGGED ENS001A 10 Gbit/s              | ens001a-rt09                                           | Redwood Institute, RWI       | Enschede |
| gen-3495             | RWL L2VPN AMS001A-RMD002A 100 Gbit/s           | ams001a-rt06, rmd002a-rt02                             | Redwood Libraries, RWL       | Amsterdam, Roermond |
| gen-3496             | BFU IP ENS001A 1 Gbit/s                        | ens001a-rt06                                           | Bluefin University, BFU      | Enschede |
| gen-3497             | BFH L2VPN ALM001A-ASV001A-RTD001A 1 Gbit/s     | asv001a-rt12, rtd001a-rt09, alm001a-rt06, rtd002a-rt10 | Bluefin Hospital, BFH        | Amstelveen, Rotterdam, Almere |
| gen-3498             | NWR L2VPN ENS002A-GRQ002A 10 Gbit/s            | ens002a-rt10, grq002a-rt01                             | Northwind Research, NWR      | Enschede, Groningen |
| gen-3499             | GFO L2VPN ALM001A-ARN001A-EHV001A 100 Gbit/s   | ehv001a-rt11, gor002a-rt01, arn001a-rt09, alm001a-rt02 | Greenfield Observatory, GFO  | Eindhoven, Gorinchem, Arnhem, Almere |
| gen-3501             | NWL LP EHV002A-GOR001A 10 Gbit/s               | ehv002a-rt08, gor001a-rt11                             | Northwind Labs, NWL          | Eindhoven, Gorinchem |
| gen-3504             | RWL SP TAGGED RTD002A 10 Gbit/s                | rtd002a-rt12                                           | Redwood Libraries, RWL       | Rotterdam |
| gen-3505             | NWL IP ALM001A 100 Gbit/s                      | alm001a-rt01                                           | Northwind Labs, NWL          | Almere |
| gen-3506             | BFU SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt10                                           | Bluefin University, BFU      | Roermond |
| gen-3508             | SLA SP TAGGED GRQ001A 100 Gbit/s               | grq001a-rt12                                           | Silverline Archives, SLA     | Groningen |
| gen-3512             | BFU IP RTD002A 10 Gbit/s                       | rtd002a-rt03                                           | Bluefin University, BFU      | Rotterdam |
| gen-3514             | GFO L2VPN ARN001A-GOR001A 1 Gbit/s             | arn001a-rt09, gor001a-rt08                             | Greenfield Observatory, GFO  | Arnhem, Gorinchem |
| gen-3515             | NWL LP ENS001A-MST002A 10 Gbit/s               | ens001a-rt08, mst002a-rt11                             | Northwind Labs, NWL          | Enschede, Maastricht |
| gen-3516             | RWL LP EHV001A-GOR001A 100 Gbit/s              | ehv001a-rt08, gor001a-rt01                             | Redwood Libraries, RWL       | Eindhoven, Gorinchem |
| gen-3517             | RWL LP GRQ001A-RTD001A 100 Gbit/s              | rtd001a-rt04, grq001a-rt08                             | Redwood Libraries, RWL       | Rotterdam, Groningen |
| gen-3518             | SLA IP ALM002A 100 Gbit/s                      | alm002a-rt07                                           | Silverline Archives, SLA     | Almere |
| gen-3519             | BFH L2VPN ARN002A-ENS001A-GRQ002A 100 Gbit/s   | grq002a-rt09, ens001a-rt01, arn002a-rt08               | Bluefin Hospital, BFH        | Groningen, Enschede, Arnhem |
| gen-3521             | RWL IP GOR001A 1 Gbit/s                        | gor001a-rt07                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-3525             | GFO SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt09                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-3526             | BFU LP RMD002A-RTD002A 100 Gbit/s              | rmd002a-rt03, rtd002a-rt01                             | Bluefin University, BFU      | Roermond, Rotterdam |
| gen-3528             | RWI LP GRQ002A-MST001A 10 Gbit/s               | grq002a-rt07, mst001a-rt03                             | Redwood Institute, RWI       | Groningen, Maastricht |
| gen-3529             | GFO L2VPN AMS001A-ARN002A-EHV001A 100 Gbit/s   | arn002a-rt04, ehv001a-rt11, ams001a-rt04               | Greenfield Observatory, GFO  | Arnhem, Eindhoven, Amsterdam |
| gen-3530             | GFO LP ASV001A-MST002A 1 Gbit/s                | asv001a-rt03, mst002a-rt10                             | Greenfield Observatory, GFO  | Amstelveen, Maastricht |
| gen-3535             | GFC L2VPN AMS001A-ASV002A-ENS001A 100 Gbit/s   | ens002a-rt10, ens001a-rt07, asv002a-rt03, ams001a-rt02 | Greenfield College, GFC      | Enschede, Amstelveen, Amsterdam |
| gen-3536             | RWI SP TAGGED ALM002A 100 Gbit/s               | alm002a-rt02                                           | Redwood Institute, RWI       | Almere |
| gen-3537             | NWL SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt11                                           | Northwind Labs, NWL          | Maastricht |
| gen-3539             | BFH L2VPN ALM001A-ASV001A-GRQ002A 1 Gbit/s     | grq002a-rt06, alm001a-rt10, asv001a-rt04, utr002a-rt05 | Bluefin Hospital, BFH        | Groningen, Almere, Amstelveen, Utrecht |
| gen-3541             | NWR LP ARN001A-EHV001A 100 Gbit/s              | arn001a-rt08, ehv001a-rt04                             | Northwind Research, NWR      | Arnhem, Eindhoven |
| gen-3542             | GFO L2VPN RTD001A-UTR002A 1 Gbit/s             | utr002a-rt07, rtd001a-rt12                             | Greenfield Observatory, GFO  | Utrecht, Rotterdam |
| gen-3543             | RWL LP EHV002A-ENS002A 1 Gbit/s                | ens002a-rt05, ehv002a-rt02                             | Redwood Libraries, RWL       | Enschede, Eindhoven |
| gen-3545             | RWL SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-3546             | GFO IP EHV002A 10 Gbit/s                       | ehv002a-rt06                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-3547             | NWL SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt06                                           | Northwind Labs, NWL          | Arnhem |
| gen-3549             | BFH LP ALM001A-ASV002A 10 Gbit/s               | asv002a-rt02, alm001a-rt10                             | Bluefin Hospital, BFH        | Amstelveen, Almere |
| gen-3551             | SLA LP AMS001A-UTR001A 1 Gbit/s                | ams001a-rt03, utr001a-rt06                             | Silverline Archives, SLA     | Amsterdam, Utrecht |
| gen-3553             | BFU L2VPN GOR002A-GRQ002A-MST002A 100 Gbit/s   | mst002a-rt10, gor002a-rt08, grq002a-rt04               | Bluefin University, BFU      | Maastricht, Gorinchem, Groningen |
| gen-3555             | NWL LP GOR001A-GRQ002A 100 Gbit/s              | gor001a-rt08, grq002a-rt07                             | Northwind Labs, NWL          | Gorinchem, Groningen |
| gen-3557             | SLA IP ALM001A 10 Gbit/s                       | alm001a-rt08                                           | Silverline Archives, SLA     | Almere |
| gen-3559             | GFC LP GRQ001A-UTR002A 1 Gbit/s                | grq001a-rt08, utr002a-rt07                             | Greenfield College, GFC      | Groningen, Utrecht |
| gen-3560             | RWL SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt03                                           | Redwood Libraries, RWL       | Groningen |
| gen-3561             | GFC L2VPN GOR002A-GRQ002A-RTD001A 10 Gbit/s    | gor002a-rt06, grq002a-rt06, rtd001a-rt04, gor002a-rt11 | Greenfield College, GFC      | Gorinchem, Groningen, Rotterdam |
| gen-3565             | BFH L2VPN GOR001A-GOR002A-RMD001A 1 Gbit/s     | rmd001a-rt07, gor002a-rt03, gor001a-rt08, rmd002a-rt10 | Bluefin Hospital, BFH        | Roermond, Gorinchem |
| gen-3566             | RWL IP ARN002A 1 Gbit/s                        | arn002a-rt07                                           | Redwood Libraries, RWL       | Arnhem |
| gen-3568             | GFC SP TAGGED RTD002A 100 Gbit/s               | rtd002a-rt03                                           | Greenfield College, GFC      | Rotterdam |
| gen-3569             | NWL SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt04                                           | Northwind Labs, NWL          | Roermond |
| gen-3570             | NWL LP EHV002A-MST001A 100 Gbit/s              | mst001a-rt10, ehv002a-rt01                             | Northwind Labs, NWL          | Maastricht, Eindhoven |
| gen-3571             | BFU IP UTR001A 100 Gbit/s                      | utr001a-rt07                                           | Bluefin University, BFU      | Utrecht |
| gen-3572             | RWL LP ARN002A-UTR001A 1 Gbit/s                | utr001a-rt07, arn002a-rt04                             | Redwood Libraries, RWL       | Utrecht, Arnhem |
| gen-3575             | RWI SP TAGGED GOR001A 10 Gbit/s                | gor001a-rt10                                           | Redwood Institute, RWI       | Gorinchem |
| gen-3577             | BFH LP MST001A-MST002A 1 Gbit/s                | mst002a-rt04, mst001a-rt01                             | Bluefin Hospital, BFH        | Maastricht |
| gen-3578             | GFO LP UTR001A-UTR002A 100 Gbit/s              | utr002a-rt06, utr001a-rt01                             | Greenfield Observatory, GFO  | Utrecht |
| gen-3588             | RWI L2VPN ALM001A-GOR002A-RMD001A 1 Gbit/s     | alm001a-rt02, rmd001a-rt09, gor002a-rt02               | Redwood Institute, RWI       | Almere, Roermond, Gorinchem |
| gen-3594             | SLM IP ALM001A 100 Gbit/s                      | alm001a-rt08                                           | Silverline Museum, SLM       | Almere |
| gen-3595             | GFC LP EHV002A-RMD001A 100 Gbit/s              | rmd001a-rt09, ehv002a-rt06                             | Greenfield College, GFC      | Roermond, Eindhoven |
| gen-3598             | BFH LP EHV001A-UTR002A 100 Gbit/s              | ehv001a-rt07, utr002a-rt02                             | Bluefin Hospital, BFH        | Eindhoven, Utrecht |
| gen-3600             | GFO SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt07                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-3604             | RWI LP ALM001A-RTD001A 10 Gbit/s               | rtd001a-rt06, alm001a-rt03                             | Redwood Institute, RWI       | Rotterdam, Almere |
| gen-3608             | BFU L2VPN ENS001A-GOR002A-RTD002A 10 Gbit/s    | rtd002a-rt01, gor002a-rt01, ens001a-rt12, utr002a-rt05 | Bluefin University, BFU      | Rotterdam, Gorinchem, Enschede, Utrecht |
| gen-3609             | BFH L2VPN ASV001A-EHV001A-GOR001A 100 Gbit/s   | utr002a-rt06, gor001a-rt03, asv001a-rt06, ehv001a-rt02 | Bluefin Hospital, BFH        | Utrecht, Gorinchem, Amstelveen, Eindhoven |
| gen-3611             | NWR LP ENS002A-ENS002A 100 Gbit/s              | ens002a-rt02, ens002a-rt06                             | Northwind Research, NWR      | Enschede |
| gen-3612             | GFC IP AMS002A 100 Gbit/s                      | ams002a-rt02                                           | Greenfield College, GFC      | Amsterdam |
| gen-3617             | SLM L2VPN ASV001A-ASV002A-GRQ001A 10 Gbit/s    | grq001a-rt02, asv001a-rt03, asv001a-rt12, asv002a-rt09 | Silverline Museum, SLM       | Groningen, Amstelveen |
| gen-3618             | RWL L2VPN MST002A-UTR001A 10 Gbit/s            | mst002a-rt04, utr001a-rt07                             | Redwood Libraries, RWL       | Maastricht, Utrecht |
| gen-3619             | BFU L2VPN GRQ001A-RMD001A-RTD001A 1 Gbit/s     | rmd001a-rt08, grq001a-rt04, rtd001a-rt05               | Bluefin University, BFU      | Roermond, Groningen, Rotterdam |
| gen-3620             | RWL L2VPN AMS001A-ARN001A-RTD002A 1 Gbit/s     | arn001a-rt10, ams001a-rt08, rtd002a-rt09               | Redwood Libraries, RWL       | Arnhem, Amsterdam, Rotterdam |
| gen-3621             | GFO IP GRQ001A 1 Gbit/s                        | grq001a-rt07                                           | Greenfield Observatory, GFO  | Groningen |
| gen-3624             | NWR SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt03                                           | Northwind Research, NWR      | Roermond |
| gen-3625             | NWR IP RMD001A 100 Gbit/s                      | rmd001a-rt09                                           | Northwind Research, NWR      | Roermond |
| gen-3627             | GFO IP ENS001A 1 Gbit/s                        | ens001a-rt10                                           | Greenfield Observatory, GFO  | Enschede |
| gen-3629             | BFU L2VPN ALM002A-RTD002A 100 Gbit/s           | alm002a-rt12, rtd002a-rt04                             | Bluefin University, BFU      | Almere, Rotterdam |
| gen-3632             | RWI IP ARN002A 1 Gbit/s                        | arn002a-rt08                                           | Redwood Institute, RWI       | Arnhem |
| gen-3633             | BFU SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt01                                           | Bluefin University, BFU      | Almere |
| gen-3635             | NWL IP RMD002A 100 Gbit/s                      | rmd002a-rt04                                           | Northwind Labs, NWL          | Roermond |
| gen-3636             | NWR LP ASV002A-RMD001A 100 Gbit/s              | asv002a-rt09, rmd001a-rt03                             | Northwind Research, NWR      | Amstelveen, Roermond |
| gen-3637             | SLA SP UNTAGGED GOR001A 10 Gbit/s              | gor001a-rt06                                           | Silverline Archives, SLA     | Gorinchem |
| gen-3641             | NWR SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt05                                           | Northwind Research, NWR      | Amstelveen |
| gen-3643             | SLM IP AMS002A 100 Gbit/s                      | ams002a-rt10                                           | Silverline Museum, SLM       | Amsterdam |
| gen-3649             | RWI SP TAGGED GRQ001A 100 Gbit/s               | grq001a-rt12                                           | Redwood Institute, RWI       | Groningen |
| gen-3652             | BFU IP GRQ001A 100 Gbit/s                      | grq001a-rt09                                           | Bluefin University, BFU      | Groningen |
| gen-3653             | BFH SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt07                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-3654             | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt02                                           | Greenfield College, GFC      | Enschede |
| gen-3659             | NWR SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt12                                           | Northwind Research, NWR      | Arnhem |
| gen-3660             | SLM SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt07                                           | Silverline Museum, SLM       | Amsterdam |
| gen-3662             | GFC LP ARN002A-GRQ002A 1 Gbit/s                | arn002a-rt02, grq002a-rt11                             | Greenfield College, GFC      | Arnhem, Groningen |
| gen-3663             | GFO LP ASV002A-ENS001A 10 Gbit/s               | asv002a-rt08, ens001a-rt04                             | Greenfield Observatory, GFO  | Amstelveen, Enschede |
| gen-3665             | NWR SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt03                                           | Northwind Research, NWR      | Eindhoven |
| gen-3666             | RWL SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt03                                           | Redwood Libraries, RWL       | Almere |
| gen-3669             | BFH SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt08                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-3670             | BFU SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt09                                           | Bluefin University, BFU      | Eindhoven |
| gen-3671             | SLA IP ARN002A 10 Gbit/s                       | arn002a-rt03                                           | Silverline Archives, SLA     | Arnhem |
| gen-3675             | SLM IP ALM001A 10 Gbit/s                       | alm001a-rt12                                           | Silverline Museum, SLM       | Almere |
| gen-3676             | BFH SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt11                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-3680             | BFU LP ARN002A-UTR001A 10 Gbit/s               | arn002a-rt11, utr001a-rt07                             | Bluefin University, BFU      | Arnhem, Utrecht |
| gen-3682             | BFU LP EHV001A-GOR002A 10 Gbit/s               | ehv001a-rt11, gor002a-rt07                             | Bluefin University, BFU      | Eindhoven, Gorinchem |
| gen-3684             | BFH IP ENS002A 10 Gbit/s                       | ens002a-rt05                                           | Bluefin Hospital, BFH        | Enschede |
| gen-3685             | SLA IP ARN002A 1 Gbit/s                        | arn002a-rt06                                           | Silverline Archives, SLA     | Arnhem |
| gen-3686             | SLM IP ARN001A 100 Gbit/s                      | arn001a-rt01                                           | Silverline Museum, SLM       | Arnhem |
| gen-3687             | BFH IP UTR002A 10 Gbit/s                       | utr002a-rt12                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-3689             | BFU LP GOR001A-RMD002A 100 Gbit/s              | gor001a-rt07, rmd002a-rt07                             | Bluefin University, BFU      | Gorinchem, Roermond |
| gen-3691             | GFO IP GOR001A 100 Gbit/s                      | gor001a-rt02                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-3692             | GFC L2VPN EHV002A-RTD002A 100 Gbit/s           | ehv002a-rt07, rtd002a-rt12                             | Greenfield College, GFC      | Eindhoven, Rotterdam |
| gen-3698             | NWL SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt11                                           | Northwind Labs, NWL          | Roermond |
| gen-3700             | RWI L2VPN AMS002A-MST001A-RTD001A 100 Gbit/s   | ams002a-rt01, mst001a-rt04, ams002a-rt05, rtd001a-rt06 | Redwood Institute, RWI       | Amsterdam, Maastricht, Rotterdam |
| gen-3701             | GFO SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt10                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-3702             | NWL IP GRQ002A 100 Gbit/s                      | grq002a-rt10                                           | Northwind Labs, NWL          | Groningen |
| gen-3703             | BFU IP UTR002A 10 Gbit/s                       | utr002a-rt10                                           | Bluefin University, BFU      | Utrecht |
| gen-3704             | RWL LP AMS002A-RTD002A 1 Gbit/s                | rtd002a-rt05, ams002a-rt11                             | Redwood Libraries, RWL       | Rotterdam, Amsterdam |
| gen-3705             | SLA L2VPN GOR002A-MST001A 100 Gbit/s           | gor002a-rt09, mst001a-rt03                             | Silverline Archives, SLA     | Gorinchem, Maastricht |
| gen-3706             | RWL LP ALM002A-UTR001A 10 Gbit/s               | utr001a-rt05, alm002a-rt01                             | Redwood Libraries, RWL       | Utrecht, Almere |
| gen-3708             | GFC LP ASV002A-ENS001A 100 Gbit/s              | asv002a-rt02, ens001a-rt10                             | Greenfield College, GFC      | Amstelveen, Enschede |
| gen-3711             | BFU LP RMD002A-RMD002A 100 Gbit/s              | rmd002a-rt11, rmd002a-rt01                             | Bluefin University, BFU      | Roermond |
| gen-3713             | RWL LP AMS001A-MST002A 1 Gbit/s                | mst002a-rt01, ams001a-rt08                             | Redwood Libraries, RWL       | Maastricht, Amsterdam |
| gen-3715             | SLM LP ALM002A-ASV002A 1 Gbit/s                | alm002a-rt01, asv002a-rt06                             | Silverline Museum, SLM       | Almere, Amstelveen |
| gen-3718             | SLM IP ALM002A 10 Gbit/s                       | alm002a-rt03                                           | Silverline Museum, SLM       | Almere |
| gen-3720             | RWI LP ALM002A-ARN001A 10 Gbit/s               | alm002a-rt12, arn001a-rt03                             | Redwood Institute, RWI       | Almere, Arnhem |
| gen-3723             | BFU SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt10                                           | Bluefin University, BFU      | Roermond |
| gen-3725             | GFO L2VPN ALM001A-EHV002A-GRQ001A 10 Gbit/s    | alm001a-rt06, ehv002a-rt10, grq001a-rt05, grq002a-rt12 | Greenfield Observatory, GFO  | Almere, Eindhoven, Groningen |
| gen-3726             | RWL IP ENS001A 10 Gbit/s                       | ens001a-rt12                                           | Redwood Libraries, RWL       | Enschede |
| gen-3728             | BFU L2VPN ALM002A-ARN001A-RMD001A 10 Gbit/s    | rtd002a-rt06, rmd001a-rt12, alm002a-rt02, arn001a-rt02 | Bluefin University, BFU      | Rotterdam, Roermond, Almere, Arnhem |
| gen-3729             | GFO L2VPN ASV001A-RMD002A 1 Gbit/s             | rmd002a-rt11, asv001a-rt02                             | Greenfield Observatory, GFO  | Roermond, Amstelveen |
| gen-3731             | GFO LP AMS002A-UTR002A 10 Gbit/s               | utr002a-rt06, ams002a-rt08                             | Greenfield Observatory, GFO  | Utrecht, Amsterdam |
| gen-3732             | RWL SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt05                                           | Redwood Libraries, RWL       | Groningen |
| gen-3736             | GFC SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt05                                           | Greenfield College, GFC      | Gorinchem |
| gen-3737             | SLM LP ALM002A-AMS001A 10 Gbit/s               | ams001a-rt03, alm002a-rt11                             | Silverline Museum, SLM       | Amsterdam, Almere |
| gen-3738             | GFC L2VPN ARN001A-ENS002A 1 Gbit/s             | arn001a-rt03, ens002a-rt08                             | Greenfield College, GFC      | Arnhem, Enschede |
| gen-3742             | NWL IP ARN001A 1 Gbit/s                        | arn001a-rt08                                           | Northwind Labs, NWL          | Arnhem |
| gen-3743             | BFU IP GOR002A 1 Gbit/s                        | gor002a-rt02                                           | Bluefin University, BFU      | Gorinchem |
| gen-3744             | BFH LP ARN001A-GOR002A 1 Gbit/s                | arn001a-rt09, gor002a-rt05                             | Bluefin Hospital, BFH        | Arnhem, Gorinchem |
| gen-3746             | SLA L2VPN ASV001A-GRQ002A-UTR001A 1 Gbit/s     | utr001a-rt09, grq002a-rt07, asv001a-rt03               | Silverline Archives, SLA     | Utrecht, Groningen, Amstelveen |
| gen-3747             | NWR IP ALM002A 1 Gbit/s                        | alm002a-rt08                                           | Northwind Research, NWR      | Almere |
| gen-3749             | GFO L2VPN ENS002A-RTD001A-UTR002A 1 Gbit/s     | utr002a-rt05, ens002a-rt02, rtd001a-rt09               | Greenfield Observatory, GFO  | Utrecht, Enschede, Rotterdam |
| gen-3752             | GFO LP AMS002A-GOR002A 10 Gbit/s               | ams002a-rt06, gor002a-rt04                             | Greenfield Observatory, GFO  | Amsterdam, Gorinchem |
| gen-3754             | GFC SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt08                                           | Greenfield College, GFC      | Utrecht |
| gen-3755             | RWI IP ENS002A 1 Gbit/s                        | ens002a-rt11                                           | Redwood Institute, RWI       | Enschede |
| gen-3756             | BFU SP TAGGED RTD001A 10 Gbit/s                | rtd001a-rt04                                           | Bluefin University, BFU      | Rotterdam |
| gen-3757             | BFH IP RMD001A 1 Gbit/s                        | rmd001a-rt02                                           | Bluefin Hospital, BFH        | Roermond |
| gen-3759             | GFO SP UNTAGGED EHV002A 10 Gbit/s              | ehv002a-rt08                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-3763             | BFH LP ENS002A-UTR002A 100 Gbit/s              | utr002a-rt09, ens002a-rt04                             | Bluefin Hospital, BFH        | Utrecht, Enschede |
| gen-3765             | GFO SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt02                                           | Greenfield Observatory, GFO  | Almere |
| gen-3768             | BFH LP ENS002A-RMD002A 1 Gbit/s                | ens002a-rt09, rmd002a-rt01                             | Bluefin Hospital, BFH        | Enschede, Roermond |
| gen-3771             | RWI L2VPN AMS002A-ARN002A-UTR002A 100 Gbit/s   | utr002a-rt02, arn002a-rt12, ams002a-rt09               | Redwood Institute, RWI       | Utrecht, Arnhem, Amsterdam |
| gen-3772             | RWI LP ARN002A-ENS001A 1 Gbit/s                | arn002a-rt11, ens001a-rt12                             | Redwood Institute, RWI       | Arnhem, Enschede |
| gen-3773             | GFC IP ASV002A 10 Gbit/s                       | asv002a-rt02                                           | Greenfield College, GFC      | Amstelveen |
| gen-3775             | BFH IP MST002A 1 Gbit/s                        | mst002a-rt10                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-3779             | BFU SP UNTAGGED UTR002A 1 Gbit/s               | utr002a-rt08                                           | Bluefin University, BFU      | Utrecht |
| gen-3780             | GFO LP ASV002A-UTR002A 100 Gbit/s              | asv002a-rt12, utr002a-rt03                             | Greenfield Observatory, GFO  | Amstelveen, Utrecht |
| gen-3781             | GFO L2VPN ASV001A-GRQ002A 10 Gbit/s            | asv001a-rt11, grq002a-rt04                             | Greenfield Observatory, GFO  | Amstelveen, Groningen |
| gen-3782             | SLM LP ALM002A-AMS002A 100 Gbit/s              | alm002a-rt09, ams002a-rt07                             | Silverline Museum, SLM       | Almere, Amsterdam |
| gen-3783             | RWL IP RMD001A 100 Gbit/s                      | rmd001a-rt04                                           | Redwood Libraries, RWL       | Roermond |
| gen-3784             | NWR LP ALM002A-ASV002A 10 Gbit/s               | alm002a-rt11, asv002a-rt05                             | Northwind Research, NWR      | Almere, Amstelveen |
| gen-3785             | SLA L2VPN ARN002A-GOR002A 10 Gbit/s            | gor002a-rt12, arn002a-rt12                             | Silverline Archives, SLA     | Gorinchem, Arnhem |
| gen-3786             | NWR L2VPN EHV002A-GOR001A-RMD001A 1 Gbit/s     | rmd001a-rt12, ehv002a-rt03, gor001a-rt11               | Northwind Research, NWR      | Roermond, Eindhoven, Gorinchem |
| gen-3788             | NWR IP RMD002A 10 Gbit/s                       | rmd002a-rt03                                           | Northwind Research, NWR      | Roermond |
| gen-3790             | GFO LP ALM002A-GOR001A 10 Gbit/s               | alm002a-rt05, gor001a-rt06                             | Greenfield Observatory, GFO  | Almere, Gorinchem |
| gen-3797             | BFU SP UNTAGGED RTD002A 1 Gbit/s               | rtd002a-rt10                                           | Bluefin University, BFU      | Rotterdam |
| gen-3798             | GFC SP UNTAGGED ENS002A 10 Gbit/s              | ens002a-rt07                                           | Greenfield College, GFC      | Enschede |
| gen-3800             | BFU IP ARN002A 10 Gbit/s                       | arn002a-rt06                                           | Bluefin University, BFU      | Arnhem |
| gen-3803             | RWI IP ALM001A 10 Gbit/s                       | alm001a-rt02                                           | Redwood Institute, RWI       | Almere |
| gen-3805             | GFO L2VPN ARN002A-GRQ002A 10 Gbit/s            | grq002a-rt02, arn002a-rt12                             | Greenfield Observatory, GFO  | Groningen, Arnhem |
| gen-3806             | SLA SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt09                                           | Silverline Archives, SLA     | Arnhem |
| gen-3810             | SLM SP TAGGED UTR001A 100 Gbit/s               | utr001a-rt05                                           | Silverline Museum, SLM       | Utrecht |
| gen-3813             | SLM LP ALM001A-UTR002A 1 Gbit/s                | utr002a-rt11, alm001a-rt10                             | Silverline Museum, SLM       | Utrecht, Almere |
| gen-3814             | RWL IP GRQ002A 10 Gbit/s                       | grq002a-rt11                                           | Redwood Libraries, RWL       | Groningen |
| gen-3815             | RWI SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt07                                           | Redwood Institute, RWI       | Arnhem |
| gen-3816             | GFO SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt06                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-3817             | RWL SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt08                                           | Redwood Libraries, RWL       | Arnhem |
| gen-3822             | RWL IP ALM001A 100 Gbit/s                      | alm001a-rt10                                           | Redwood Libraries, RWL       | Almere |
| gen-3826             | SLA LP ARN001A-GRQ001A 10 Gbit/s               | grq001a-rt01, arn001a-rt03                             | Silverline Archives, SLA     | Groningen, Arnhem |
| gen-3830             | RWL SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt01                                           | Redwood Libraries, RWL       | Groningen |
| gen-3837             | RWL L2VPN AMS001A-EHV002A 1 Gbit/s             | ehv002a-rt04, ams001a-rt03                             | Redwood Libraries, RWL       | Eindhoven, Amsterdam |
| gen-3840             | NWL SP TAGGED GRQ002A 1 Gbit/s                 | grq002a-rt01                                           | Northwind Labs, NWL          | Groningen |
| gen-3841             | BFU SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt01                                           | Bluefin University, BFU      | Almere |
| gen-3843             | RWL IP GRQ002A 100 Gbit/s                      | grq002a-rt04                                           | Redwood Libraries, RWL       | Groningen |
| gen-3845             | NWL L2VPN ARN001A-GOR001A 1 Gbit/s             | arn001a-rt07, gor001a-rt12                             | Northwind Labs, NWL          | Arnhem, Gorinchem |
| gen-3848             | RWL L2VPN ALM002A-AMS001A-RMD002A 1 Gbit/s     | rmd002a-rt03, alm002a-rt07, ams001a-rt05               | Redwood Libraries, RWL       | Roermond, Almere, Amsterdam |
| gen-3849             | BFU SP TAGGED RMD001A 1 Gbit/s                 | rmd001a-rt06                                           | Bluefin University, BFU      | Roermond |
| gen-3851             | SLM LP ARN001A-ASV002A 10 Gbit/s               | asv002a-rt01, arn001a-rt06                             | Silverline Museum, SLM       | Amstelveen, Arnhem |
| gen-3854             | RWL IP GOR001A 1 Gbit/s                        | gor001a-rt10                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-3855             | GFC L2VPN ALM002A-AMS002A-GRQ002A 100 Gbit/s   | grq002a-rt01, alm002a-rt02, ams002a-rt05               | Greenfield College, GFC      | Groningen, Almere, Amsterdam |
| gen-3856             | RWI SP UNTAGGED ARN001A 1 Gbit/s               | arn001a-rt10                                           | Redwood Institute, RWI       | Arnhem |
| gen-3858             | RWL LP ALM001A-GRQ001A 10 Gbit/s               | alm001a-rt10, grq001a-rt02                             | Redwood Libraries, RWL       | Almere, Groningen |
| gen-3859             | BFU SP UNTAGGED ENS001A 100 Gbit/s             | ens001a-rt02                                           | Bluefin University, BFU      | Enschede |
| gen-3862             | BFU L2VPN ARN001A-ARN002A-MST001A 100 Gbit/s   | mst001a-rt03, arn001a-rt10, arn002a-rt03               | Bluefin University, BFU      | Maastricht, Arnhem |
| gen-3863             | RWI IP EHV002A 100 Gbit/s                      | ehv002a-rt08                                           | Redwood Institute, RWI       | Eindhoven |
| gen-3864             | SLM LP ARN002A-UTR002A 100 Gbit/s              | arn002a-rt09, utr002a-rt06                             | Silverline Museum, SLM       | Arnhem, Utrecht |
| gen-3865             | SLA SP TAGGED UTR001A 100 Gbit/s               | utr001a-rt08                                           | Silverline Archives, SLA     | Utrecht |
| gen-3869             | SLM LP GRQ002A-UTR001A 100 Gbit/s              | grq002a-rt11, utr001a-rt03                             | Silverline Museum, SLM       | Groningen, Utrecht |
| gen-3871             | GFO L2VPN ALM002A-ARN002A 100 Gbit/s           | alm002a-rt03, arn002a-rt04                             | Greenfield Observatory, GFO  | Almere, Arnhem |
| gen-3872             | BFU LP ASV001A-ASV002A 10 Gbit/s               | asv002a-rt04, asv001a-rt11                             | Bluefin University, BFU      | Amstelveen |
| gen-3873             | BFU SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt07                                           | Bluefin University, BFU      | Arnhem |
| gen-3874             | GFC L2VPN EHV002A-GRQ002A-RMD002A 10 Gbit/s    | ehv002a-rt09, rmd002a-rt07, grq002a-rt05               | Greenfield College, GFC      | Eindhoven, Roermond, Groningen |
| gen-3875             | NWL SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt07                                           | Northwind Labs, NWL          | Arnhem |
| gen-3876             | BFU L2VPN EHV001A-GRQ002A-MST001A 100 Gbit/s   | grq002a-rt08, ehv001a-rt09, mst001a-rt01               | Bluefin University, BFU      | Groningen, Eindhoven, Maastricht |
| gen-3878             | GFO IP UTR002A 1 Gbit/s                        | utr002a-rt11                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-3879             | GFC LP ARN002A-ASV001A 10 Gbit/s               | arn002a-rt03, asv001a-rt11                             | Greenfield College, GFC      | Arnhem, Amstelveen |
| gen-3881             | NWR IP EHV002A 100 Gbit/s                      | ehv002a-rt01                                           | Northwind Research, NWR      | Eindhoven |
| gen-3882             | RWL IP RMD001A 100 Gbit/s                      | rmd001a-rt10                                           | Redwood Libraries, RWL       | Roermond |
| gen-3883             | SLM IP AMS002A 1 Gbit/s                        | ams002a-rt06                                           | Silverline Museum, SLM       | Amsterdam |
| gen-3885             | SLA IP ASV002A 100 Gbit/s                      | asv002a-rt06                                           | Silverline Archives, SLA     | Amstelveen |
| gen-3886             | BFU IP ASV002A 10 Gbit/s                       | asv002a-rt10                                           | Bluefin University, BFU      | Amstelveen |
| gen-3888             | NWL IP ENS002A 100 Gbit/s                      | ens002a-rt12                                           | Northwind Labs, NWL          | Enschede |
| gen-3892             | BFU IP ARN002A 10 Gbit/s                       | arn002a-rt08                                           | Bluefin University, BFU      | Arnhem |
| gen-3894             | GFO L2VPN ARN001A-ARN002A 10 Gbit/s            | arn001a-rt12, arn002a-rt06                             | Greenfield Observatory, GFO  | Arnhem |
| gen-3896             | NWL IP GRQ001A 100 Gbit/s                      | grq001a-rt12                                           | Northwind Labs, NWL          | Groningen |
| gen-3898             | RWI LP GOR002A-UTR001A 100 Gbit/s              | utr001a-rt09, gor002a-rt06                             | Redwood Institute, RWI       | Utrecht, Gorinchem |
| gen-3899             | SLM IP ARN002A 100 Gbit/s                      | arn002a-rt08                                           | Silverline Museum, SLM       | Arnhem |
| gen-3900             | NWL L2VPN ALM002A-GOR001A 1 Gbit/s             | alm002a-rt02, gor001a-rt06, gor001a-rt02               | Northwind Labs, NWL          | Almere, Gorinchem |
| gen-3903             | BFU IP RMD001A 1 Gbit/s                        | rmd001a-rt08                                           | Bluefin University, BFU      | Roermond |
| gen-3904             | RWL SP UNTAGGED ENS001A 1 Gbit/s               | ens001a-rt02                                           | Redwood Libraries, RWL       | Enschede |
| gen-3906             | RWI IP UTR001A 10 Gbit/s                       | utr001a-rt01                                           | Redwood Institute, RWI       | Utrecht |
| gen-3907             | RWL IP MST002A 10 Gbit/s                       | mst002a-rt02                                           | Redwood Libraries, RWL       | Maastricht |
| gen-3908             | GFO LP EHV001A-ENS001A 1 Gbit/s                | ens001a-rt01, ehv001a-rt01                             | Greenfield Observatory, GFO  | Enschede, Eindhoven |
| gen-3912             | SLA SP UNTAGGED UTR002A 10 Gbit/s              | utr002a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-3914             | BFH LP GRQ002A-RTD001A 100 Gbit/s              | rtd001a-rt10, grq002a-rt04                             | Bluefin Hospital, BFH        | Rotterdam, Groningen |
| gen-3915             | RWI IP RTD001A 1 Gbit/s                        | rtd001a-rt05                                           | Redwood Institute, RWI       | Rotterdam |
| gen-3919             | RWI IP GRQ001A 100 Gbit/s                      | grq001a-rt01                                           | Redwood Institute, RWI       | Groningen |
| gen-3920             | RWI LP UTR001A-UTR001A 10 Gbit/s               | utr001a-rt06, utr001a-rt05                             | Redwood Institute, RWI       | Utrecht |
| gen-3921             | BFU SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt07                                           | Bluefin University, BFU      | Amstelveen |
| gen-3924             | SLA SP UNTAGGED GOR001A 1 Gbit/s               | gor001a-rt09                                           | Silverline Archives, SLA     | Gorinchem |
| gen-3927             | GFC LP AMS001A-RTD002A 10 Gbit/s               | rtd002a-rt07, ams001a-rt09                             | Greenfield College, GFC      | Rotterdam, Amsterdam |
| gen-3930             | BFU IP ASV001A 100 Gbit/s                      | asv001a-rt02                                           | Bluefin University, BFU      | Amstelveen |
| gen-3931             | BFH L2VPN EHV002A-GOR002A-GRQ002A 100 Gbit/s   | gor002a-rt01, ehv002a-rt07, grq002a-rt08, rtd002a-rt05 | Bluefin Hospital, BFH        | Gorinchem, Eindhoven, Groningen, Rotterdam |
| gen-3934             | RWI LP EHV001A-RMD001A 10 Gbit/s               | rmd001a-rt02, ehv001a-rt02                             | Redwood Institute, RWI       | Roermond, Eindhoven |
| gen-3938             | BFH IP GOR002A 1 Gbit/s                        | gor002a-rt12                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-3939             | SLA L2VPN ARN001A-ARN002A 10 Gbit/s            | arn001a-rt03, arn002a-rt02                             | Silverline Archives, SLA     | Arnhem |
| gen-3940             | RWL LP EHV001A-RMD002A 100 Gbit/s              | ehv001a-rt12, rmd002a-rt12                             | Redwood Libraries, RWL       | Eindhoven, Roermond |
| gen-3942             | BFH SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt12                                           | Bluefin Hospital, BFH        | Enschede |
| gen-3945             | GFO L2VPN ALM002A-ENS002A-GOR002A 10 Gbit/s    | gor002a-rt07, alm002a-rt02, ens002a-rt11, rmd002a-rt04 | Greenfield Observatory, GFO  | Gorinchem, Almere, Enschede, Roermond |
| gen-3949             | NWL SP TAGGED ASV001A 100 Gbit/s               | asv001a-rt08                                           | Northwind Labs, NWL          | Amstelveen |
| gen-3950             | RWL IP EHV002A 100 Gbit/s                      | ehv002a-rt10                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-3951             | GFC SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt10                                           | Greenfield College, GFC      | Eindhoven |
| gen-3952             | BFU IP ENS002A 1 Gbit/s                        | ens002a-rt06                                           | Bluefin University, BFU      | Enschede |
| gen-3956             | GFC L2VPN ALM002A-ARN002A-RTD002A 100 Gbit/s   | rtd002a-rt08, arn002a-rt05, alm002a-rt08               | Greenfield College, GFC      | Rotterdam, Arnhem, Almere |
| gen-3958             | NWL SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt11                                           | Northwind Labs, NWL          | Almere |
| gen-3959             | NWR SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt05                                           | Northwind Research, NWR      | Almere |
| gen-3961             | NWR SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt01                                           | Northwind Research, NWR      | Almere |
| gen-3962             | RWL SP TAGGED ENS001A 100 Gbit/s               | ens001a-rt06                                           | Redwood Libraries, RWL       | Enschede |
| gen-3963             | NWR IP ARN001A 1 Gbit/s                        | arn001a-rt03                                           | Northwind Research, NWR      | Arnhem |
| gen-3965             | BFH IP ASV001A 10 Gbit/s                       | asv001a-rt06                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-3966             | GFC L2VPN ALM002A-GRQ002A-UTR002A 1 Gbit/s     | alm002a-rt05, grq002a-rt06, utr002a-rt08               | Greenfield College, GFC      | Almere, Groningen, Utrecht |
| gen-3967             | GFO IP UTR002A 100 Gbit/s                      | utr002a-rt03                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-3968             | BFH SP TAGGED ARN001A 100 Gbit/s               | arn001a-rt02                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-3972             | SLM SP TAGGED GRQ001A 1 Gbit/s                 | grq001a-rt11                                           | Silverline Museum, SLM       | Groningen |
| gen-3974             | BFH SP UNTAGGED RMD001A 100 Gbit/s             | rmd001a-rt08                                           | Bluefin Hospital, BFH        | Roermond |
| gen-3978             | BFU IP ASV002A 100 Gbit/s                      | asv002a-rt05                                           | Bluefin University, BFU      | Amstelveen |
| gen-3979             | RWL L2VPN ENS001A-MST002A-RMD002A 100 Gbit/s   | rtd002a-rt04, rmd002a-rt08, ens001a-rt10, mst002a-rt02 | Redwood Libraries, RWL       | Rotterdam, Roermond, Enschede, Maastricht |
| gen-3981             | GFO SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt12                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-3982             | BFU SP UNTAGGED ARN001A 10 Gbit/s              | arn001a-rt12                                           | Bluefin University, BFU      | Arnhem |
| gen-3984             | NWR SP TAGGED GRQ002A 10 Gbit/s                | grq002a-rt12                                           | Northwind Research, NWR      | Groningen |
| gen-3987             | BFH LP ARN001A-UTR002A 100 Gbit/s              | utr002a-rt04, arn001a-rt06                             | Bluefin Hospital, BFH        | Utrecht, Arnhem |
| gen-3989             | SLM L2VPN ARN002A-MST002A 100 Gbit/s           | mst002a-rt08, arn002a-rt08                             | Silverline Museum, SLM       | Maastricht, Arnhem |
| gen-3992             | GFO LP ENS002A-GOR001A 10 Gbit/s               | gor001a-rt11, ens002a-rt01                             | Greenfield Observatory, GFO  | Gorinchem, Enschede |
| gen-3995             | BFU IP GRQ002A 1 Gbit/s                        | grq002a-rt11                                           | Bluefin University, BFU      | Groningen |
| gen-3998             | BFU LP ALM001A-ALM002A 1 Gbit/s                | alm002a-rt09, alm001a-rt05                             | Bluefin University, BFU      | Almere |
| gen-4003             | NWR LP EHV001A-MST001A 10 Gbit/s               | mst001a-rt02, ehv001a-rt07                             | Northwind Research, NWR      | Maastricht, Eindhoven |
| gen-4004             | GFC L2VPN AMS001A-RTD001A 10 Gbit/s            | ams001a-rt02, rtd001a-rt02                             | Greenfield College, GFC      | Amsterdam, Rotterdam |
| gen-4006             | NWR SP UNTAGGED ARN001A 100 Gbit/s             | arn001a-rt10                                           | Northwind Research, NWR      | Arnhem |
| gen-4010             | RWL SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt05                                           | Redwood Libraries, RWL       | Utrecht |
| gen-4011             | RWL LP ARN002A-GRQ002A 100 Gbit/s              | grq002a-rt04, arn002a-rt11                             | Redwood Libraries, RWL       | Groningen, Arnhem |
| gen-4012             | BFH L2VPN EHV002A-GRQ002A-MST002A 1 Gbit/s     | grq002a-rt01, mst002a-rt09, rtd002a-rt08, ehv002a-rt12 | Bluefin Hospital, BFH        | Groningen, Maastricht, Rotterdam, Eindhoven |
| gen-4017             | NWR LP EHV001A-GRQ002A 1 Gbit/s                | grq002a-rt05, ehv001a-rt04                             | Northwind Research, NWR      | Groningen, Eindhoven |
| gen-4018             | BFU SP TAGGED ALM002A 1 Gbit/s                 | alm002a-rt12                                           | Bluefin University, BFU      | Almere |
| gen-4019             | GFC L2VPN GOR002A-MST002A 10 Gbit/s            | mst002a-rt04, gor002a-rt12                             | Greenfield College, GFC      | Maastricht, Gorinchem |
| gen-4020             | NWL LP EHV002A-ENS002A 100 Gbit/s              | ehv002a-rt08, ens002a-rt04                             | Northwind Labs, NWL          | Eindhoven, Enschede |
| gen-4023             | BFU SP UNTAGGED RMD002A 10 Gbit/s              | rmd002a-rt01                                           | Bluefin University, BFU      | Roermond |
| gen-4025             | BFU SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt10                                           | Bluefin University, BFU      | Maastricht |
| gen-4026             | GFC LP ASV002A-GRQ001A 10 Gbit/s               | grq001a-rt07, asv002a-rt04                             | Greenfield College, GFC      | Groningen, Amstelveen |
| gen-4028             | RWL LP EHV001A-RMD001A 100 Gbit/s              | ehv001a-rt10, rmd001a-rt12                             | Redwood Libraries, RWL       | Eindhoven, Roermond |
| gen-4030             | BFU IP ARN002A 1 Gbit/s                        | arn002a-rt11                                           | Bluefin University, BFU      | Arnhem |
| gen-4033             | BFH LP ASV001A-UTR001A 100 Gbit/s              | utr001a-rt03, asv001a-rt04                             | Bluefin Hospital, BFH        | Utrecht, Amstelveen |
| gen-4035             | GFC LP ENS001A-UTR001A 10 Gbit/s               | utr001a-rt10, ens001a-rt07                             | Greenfield College, GFC      | Utrecht, Enschede |
| gen-4036             | RWI SP UNTAGGED ENS001A 100 Gbit/s             | ens001a-rt07                                           | Redwood Institute, RWI       | Enschede |
| gen-4037             | NWR SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt10                                           | Northwind Research, NWR      | Gorinchem |
| gen-4038             | BFH SP UNTAGGED EHV002A 100 Gbit/s             | ehv002a-rt08                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-4043             | GFO LP ASV002A-EHV001A 10 Gbit/s               | asv002a-rt01, ehv001a-rt06                             | Greenfield Observatory, GFO  | Amstelveen, Eindhoven |
| gen-4044             | GFC SP UNTAGGED RMD001A 1 Gbit/s               | rmd001a-rt07                                           | Greenfield College, GFC      | Roermond |
| gen-4046             | SLM SP UNTAGGED ALM001A 100 Gbit/s             | alm001a-rt06                                           | Silverline Museum, SLM       | Almere |
| gen-4048             | GFC L2VPN EHV002A-ENS002A-RMD001A 10 Gbit/s    | rmd001a-rt09, ehv002a-rt10, ens002a-rt04, rtd001a-rt08 | Greenfield College, GFC      | Roermond, Eindhoven, Enschede, Rotterdam |
| gen-4049             | BFH LP ALM001A-UTR002A 1 Gbit/s                | alm001a-rt08, utr002a-rt08                             | Bluefin Hospital, BFH        | Almere, Utrecht |
| gen-4052             | GFO LP EHV002A-UTR002A 100 Gbit/s              | utr002a-rt09, ehv002a-rt08                             | Greenfield Observatory, GFO  | Utrecht, Eindhoven |
| gen-4053             | SLA IP ASV002A 10 Gbit/s                       | asv002a-rt06                                           | Silverline Archives, SLA     | Amstelveen |
| gen-4055             | SLA LP ARN002A-UTR001A 10 Gbit/s               | utr001a-rt07, arn002a-rt05                             | Silverline Archives, SLA     | Utrecht, Arnhem |
| gen-4056             | GFC LP MST002A-RTD002A 10 Gbit/s               | mst002a-rt07, rtd002a-rt07                             | Greenfield College, GFC      | Maastricht, Rotterdam |
| gen-4057             | GFO L2VPN ASV001A-ASV002A-EHV001A 10 Gbit/s    | asv002a-rt01, ehv001a-rt02, asv001a-rt09, gor002a-rt10 | Greenfield Observatory, GFO  | Amstelveen, Eindhoven, Gorinchem |
| gen-4058             | SLA SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt07                                           | Silverline Archives, SLA     | Amstelveen |
| gen-4059             | GFC L2VPN ENS002A 1 Gbit/s                     | ens002a-rt03, ens002a-rt11, ens002a-rt12               | Greenfield College, GFC      | Enschede |
| gen-4060             | RWI SP TAGGED UTR002A 100 Gbit/s               | utr002a-rt11                                           | Redwood Institute, RWI       | Utrecht |
| gen-4062             | BFH LP ASV002A-ENS002A 100 Gbit/s              | ens002a-rt07, asv002a-rt09                             | Bluefin Hospital, BFH        | Enschede, Amstelveen |
| gen-4064             | GFC IP ENS002A 100 Gbit/s                      | ens002a-rt02                                           | Greenfield College, GFC      | Enschede |
| gen-4065             | BFH IP RTD001A 1 Gbit/s                        | rtd001a-rt06                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4068             | BFH L2VPN ALM002A-EHV002A-GOR002A 100 Gbit/s   | alm002a-rt05, ehv002a-rt12, gor002a-rt08               | Bluefin Hospital, BFH        | Almere, Eindhoven, Gorinchem |
| gen-4070             | BFU SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt11                                           | Bluefin University, BFU      | Maastricht |
| gen-4071             | RWI L2VPN EHV002A-ENS002A-GRQ002A 100 Gbit/s   | rmd002a-rt04, ens002a-rt08, ehv002a-rt04, grq002a-rt09 | Redwood Institute, RWI       | Roermond, Enschede, Eindhoven, Groningen |
| gen-4078             | NWR SP TAGGED ASV002A 100 Gbit/s               | asv002a-rt10                                           | Northwind Research, NWR      | Amstelveen |
| gen-4079             | GFO SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt11                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-4080             | BFH IP ARN002A 10 Gbit/s                       | arn002a-rt04                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-4083             | RWL SP UNTAGGED MST002A 100 Gbit/s             | mst002a-rt11                                           | Redwood Libraries, RWL       | Maastricht |
| gen-4084             | RWL SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt04                                           | Redwood Libraries, RWL       | Enschede |
| gen-4085             | GFC L2VPN ASV002A-GOR001A-RMD002A 1 Gbit/s     | asv002a-rt10, rmd002a-rt04, gor001a-rt04               | Greenfield College, GFC      | Amstelveen, Roermond, Gorinchem |
| gen-4087             | GFC L2VPN ASV002A-RMD001A-UTR002A 1 Gbit/s     | rmd001a-rt05, asv002a-rt09, utr002a-rt09               | Greenfield College, GFC      | Roermond, Amstelveen, Utrecht |
| gen-4089             | SLA IP MST002A 100 Gbit/s                      | mst002a-rt04                                           | Silverline Archives, SLA     | Maastricht |
| gen-4090             | RWI IP MST001A 10 Gbit/s                       | mst001a-rt02                                           | Redwood Institute, RWI       | Maastricht |
| gen-4092             | GFC IP AMS001A 100 Gbit/s                      | ams001a-rt02                                           | Greenfield College, GFC      | Amsterdam |
| gen-4096             | GFO L2VPN ENS002A-GRQ002A-MST001A 1 Gbit/s     | grq002a-rt08, ens002a-rt11, mst001a-rt01               | Greenfield Observatory, GFO  | Groningen, Enschede, Maastricht |
| gen-4097             | NWR IP ASV002A 10 Gbit/s                       | asv002a-rt03                                           | Northwind Research, NWR      | Amstelveen |
| gen-4098             | GFO LP EHV001A-EHV002A 1 Gbit/s                | ehv001a-rt08, ehv002a-rt04                             | Greenfield Observatory, GFO  | Eindhoven |
| gen-4099             | RWL SP UNTAGGED RTD002A 1 Gbit/s               | rtd002a-rt11                                           | Redwood Libraries, RWL       | Rotterdam |
| gen-4100             | GFO LP GOR002A-UTR002A 10 Gbit/s               | gor002a-rt03, utr002a-rt02                             | Greenfield Observatory, GFO  | Gorinchem, Utrecht |
| gen-4102             | BFU IP ENS001A 10 Gbit/s                       | ens001a-rt05                                           | Bluefin University, BFU      | Enschede |
| gen-4105             | BFU IP ASV001A 1 Gbit/s                        | asv001a-rt08                                           | Bluefin University, BFU      | Amstelveen |
| gen-4107             | GFO L2VPN ARN001A-ENS001A-ENS002A 100 Gbit/s   | ens001a-rt10, mst001a-rt09, ens002a-rt05, arn001a-rt03 | Greenfield Observatory, GFO  | Enschede, Maastricht, Arnhem |
| gen-4109             | GFC IP MST001A 1 Gbit/s                        | mst001a-rt11                                           | Greenfield College, GFC      | Maastricht |
| gen-4110             | RWI LP GOR002A-GRQ001A 100 Gbit/s              | grq001a-rt07, gor002a-rt06                             | Redwood Institute, RWI       | Groningen, Gorinchem |
| gen-4112             | SLA L2VPN AMS001A-AMS002A-GOR002A 100 Gbit/s   | ams002a-rt08, ams001a-rt02, gor002a-rt05               | Silverline Archives, SLA     | Amsterdam, Gorinchem |
| gen-4114             | NWL SP TAGGED ENS002A 100 Gbit/s               | ens002a-rt01                                           | Northwind Labs, NWL          | Enschede |
| gen-4118             | BFU IP RTD001A 10 Gbit/s                       | rtd001a-rt02                                           | Bluefin University, BFU      | Rotterdam |
| gen-4123             | RWL LP GOR002A-GRQ002A 1 Gbit/s                | gor002a-rt09, grq002a-rt11                             | Redwood Libraries, RWL       | Gorinchem, Groningen |
| gen-4125             | BFU LP MST001A-UTR002A 10 Gbit/s               | utr002a-rt10, mst001a-rt02                             | Bluefin University, BFU      | Utrecht, Maastricht |
| gen-4128             | BFH LP ASV002A-ASV002A 100 Gbit/s              | asv002a-rt02                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4129             | RWL L2VPN ALM002A-GOR002A-GRQ002A 1 Gbit/s     | alm002a-rt08, gor002a-rt10, rtd001a-rt09, grq002a-rt08 | Redwood Libraries, RWL       | Almere, Gorinchem, Rotterdam, Groningen |
| gen-4130             | SLA IP ARN001A 10 Gbit/s                       | arn001a-rt05                                           | Silverline Archives, SLA     | Arnhem |
| gen-4131             | RWL LP AMS002A-ENS002A 100 Gbit/s              | ens002a-rt11, ams002a-rt10                             | Redwood Libraries, RWL       | Enschede, Amsterdam |
| gen-4134             | NWL LP GRQ001A-GRQ002A 10 Gbit/s               | grq002a-rt09, grq001a-rt04                             | Northwind Labs, NWL          | Groningen |
| gen-4135             | SLM IP UTR001A 100 Gbit/s                      | utr001a-rt11                                           | Silverline Museum, SLM       | Utrecht |
| gen-4136             | SLA L2VPN GOR001A-GRQ002A 10 Gbit/s            | gor001a-rt03, grq002a-rt09                             | Silverline Archives, SLA     | Gorinchem, Groningen |
| gen-4137             | BFH IP RTD001A 10 Gbit/s                       | rtd001a-rt03                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4138             | NWL SP UNTAGGED GRQ001A 10 Gbit/s              | grq001a-rt12                                           | Northwind Labs, NWL          | Groningen |
| gen-4139             | BFH IP ALM002A 1 Gbit/s                        | alm002a-rt07                                           | Bluefin Hospital, BFH        | Almere |
| gen-4143             | GFO L2VPN ALM001A-ENS001A-GOR002A 100 Gbit/s   | utr002a-rt10, alm001a-rt03, ens001a-rt02, gor002a-rt01 | Greenfield Observatory, GFO  | Utrecht, Almere, Enschede, Gorinchem |
| gen-4144             | RWL LP ARN001A-ENS002A 100 Gbit/s              | arn001a-rt01, ens002a-rt03                             | Redwood Libraries, RWL       | Arnhem, Enschede |
| gen-4145             | BFU SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt08                                           | Bluefin University, BFU      | Maastricht |
| gen-4147             | RWI LP AMS002A-GOR001A 1 Gbit/s                | gor001a-rt10, ams002a-rt07                             | Redwood Institute, RWI       | Gorinchem, Amsterdam |
| gen-4148             | BFU SP TAGGED MST001A 100 Gbit/s               | mst001a-rt02                                           | Bluefin University, BFU      | Maastricht |
| gen-4150             | BFU SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt08                                           | Bluefin University, BFU      | Almere |
| gen-4154             | GFO LP ALM002A-ENS001A 100 Gbit/s              | alm002a-rt03, ens001a-rt12                             | Greenfield Observatory, GFO  | Almere, Enschede |
| gen-4156             | SLA IP UTR002A 100 Gbit/s                      | utr002a-rt02                                           | Silverline Archives, SLA     | Utrecht |
| gen-4159             | NWR LP ENS001A-GOR001A 10 Gbit/s               | gor001a-rt02, ens001a-rt04                             | Northwind Research, NWR      | Gorinchem, Enschede |
| gen-4163             | NWR L2VPN GOR001A-GOR002A-RMD002A 10 Gbit/s    | gor002a-rt02, rmd002a-rt04, gor001a-rt08               | Northwind Research, NWR      | Gorinchem, Roermond |
| gen-4164             | SLM IP AMS002A 100 Gbit/s                      | ams002a-rt11                                           | Silverline Museum, SLM       | Amsterdam |
| gen-4166             | BFH IP GOR002A 100 Gbit/s                      | gor002a-rt10                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-4167             | BFU L2VPN ASV001A-ASV002A-EHV001A 100 Gbit/s   | grq002a-rt02, ehv001a-rt06, asv002a-rt12, asv001a-rt10 | Bluefin University, BFU      | Groningen, Eindhoven, Amstelveen |
| gen-4172             | RWL L2VPN GOR002A-RMD001A-RMD002A 100 Gbit/s   | rmd001a-rt05, gor002a-rt10, rmd002a-rt04               | Redwood Libraries, RWL       | Roermond, Gorinchem |
| gen-4173             | RWL L2VPN ARN001A-ENS002A-RMD001A 100 Gbit/s   | ens002a-rt06, rmd001a-rt12, arn001a-rt11               | Redwood Libraries, RWL       | Enschede, Roermond, Arnhem |
| gen-4181             | BFH LP EHV001A-EHV001A 100 Gbit/s              | ehv001a-rt10, ehv001a-rt09                             | Bluefin Hospital, BFH        | Eindhoven |
| gen-4183             | BFU LP ALM002A-ASV001A 100 Gbit/s              | alm002a-rt12, asv001a-rt10                             | Bluefin University, BFU      | Almere, Amstelveen |
| gen-4185             | BFU L2VPN ALM001A-GOR001A 1 Gbit/s             | alm001a-rt06, gor001a-rt10                             | Bluefin University, BFU      | Almere, Gorinchem |
| gen-4186             | BFH L2VPN ASV001A-UTR001A 100 Gbit/s           | utr001a-rt01, asv001a-rt05                             | Bluefin Hospital, BFH        | Utrecht, Amstelveen |
| gen-4188             | BFH LP ALM001A-UTR002A 10 Gbit/s               | utr002a-rt05, alm001a-rt11                             | Bluefin Hospital, BFH        | Utrecht, Almere |
| gen-4191             | GFO IP GOR002A 1 Gbit/s                        | gor002a-rt04                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-4194             | NWR SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt11                                           | Northwind Research, NWR      | Amstelveen |
| gen-4196             | GFC SP TAGGED UTR001A 1 Gbit/s                 | utr001a-rt10                                           | Greenfield College, GFC      | Utrecht |
| gen-4198             | BFU IP ENS002A 1 Gbit/s                        | ens002a-rt05                                           | Bluefin University, BFU      | Enschede |
| gen-4200             | GFO L2VPN ALM001A-AMS002A-GRQ001A 10 Gbit/s    | alm001a-rt09, rmd001a-rt10, ams002a-rt03, grq001a-rt04 | Greenfield Observatory, GFO  | Almere, Roermond, Amsterdam, Groningen |
| gen-4201             | NWR IP ARN002A 10 Gbit/s                       | arn002a-rt09                                           | Northwind Research, NWR      | Arnhem |
| gen-4203             | BFH L2VPN ALM001A-RMD001A 100 Gbit/s           | alm001a-rt09, rmd001a-rt12                             | Bluefin Hospital, BFH        | Almere, Roermond |
| gen-4205             | BFU SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt11                                           | Bluefin University, BFU      | Gorinchem |
| gen-4206             | BFH SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt12                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4207             | SLM SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt12                                           | Silverline Museum, SLM       | Arnhem |
| gen-4208             | BFH SP TAGGED ALM002A 10 Gbit/s                | alm002a-rt09                                           | Bluefin Hospital, BFH        | Almere |
| gen-4212             | GFC IP ENS002A 1 Gbit/s                        | ens002a-rt03                                           | Greenfield College, GFC      | Enschede |
| gen-4213             | BFH L2VPN ASV002A-GOR001A 10 Gbit/s            | asv002a-rt02, gor001a-rt11                             | Bluefin Hospital, BFH        | Amstelveen, Gorinchem |
| gen-4215             | NWL SP TAGGED GRQ002A 100 Gbit/s               | grq002a-rt07                                           | Northwind Labs, NWL          | Groningen |
| gen-4216             | NWR IP EHV001A 10 Gbit/s                       | ehv001a-rt06                                           | Northwind Research, NWR      | Eindhoven |
| gen-4217             | NWL IP ALM001A 10 Gbit/s                       | alm001a-rt02                                           | Northwind Labs, NWL          | Almere |
| gen-4219             | SLA SP UNTAGGED ASV001A 10 Gbit/s              | asv001a-rt06                                           | Silverline Archives, SLA     | Amstelveen |
| gen-4221             | GFC L2VPN EHV001A-GOR002A 1 Gbit/s             | gor002a-rt06, gor002a-rt02, ehv001a-rt09               | Greenfield College, GFC      | Gorinchem, Eindhoven |
| gen-4222             | NWL SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt07                                           | Northwind Labs, NWL          | Almere |
| gen-4224             | RWI L2VPN ARN001A-UTR002A 100 Gbit/s           | utr002a-rt07, arn001a-rt12                             | Redwood Institute, RWI       | Utrecht, Arnhem |
| gen-4226             | GFO IP GOR001A 1 Gbit/s                        | gor001a-rt05                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-4227             | BFU LP GOR002A-RMD001A 100 Gbit/s              | gor002a-rt08, rmd001a-rt04                             | Bluefin University, BFU      | Gorinchem, Roermond |
| gen-4229             | RWI LP AMS001A-AMS002A 1 Gbit/s                | ams002a-rt06, ams001a-rt06                             | Redwood Institute, RWI       | Amsterdam |
| gen-4234             | GFC LP ALM002A-EHV002A 10 Gbit/s               | ehv002a-rt12, alm002a-rt10                             | Greenfield College, GFC      | Eindhoven, Almere |
| gen-4235             | BFH SP UNTAGGED EHV001A 100 Gbit/s             | ehv001a-rt11                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-4239             | SLM LP ALM001A-MST001A 100 Gbit/s              | alm001a-rt02, mst001a-rt02                             | Silverline Museum, SLM       | Almere, Maastricht |
| gen-4240             | RWL LP ARN002A-RTD001A 10 Gbit/s               | rtd001a-rt12, arn002a-rt06                             | Redwood Libraries, RWL       | Rotterdam, Arnhem |
| gen-4241             | GFO L2VPN ARN002A-GOR002A-RTD002A 1 Gbit/s     | rtd002a-rt05, gor002a-rt07, arn002a-rt07               | Greenfield Observatory, GFO  | Rotterdam, Gorinchem, Arnhem |
| gen-4242             | RWI SP UNTAGGED AMS001A 100 Gbit/s             | ams001a-rt06                                           | Redwood Institute, RWI       | Amsterdam |
| gen-4244             | RWI SP TAGGED GOR001A 100 Gbit/s               | gor001a-rt11                                           | Redwood Institute, RWI       | Gorinchem |
| gen-4245             | RWL L2VPN RTD001A-UTR002A 1 Gbit/s             | rtd001a-rt06, utr002a-rt05                             | Redwood Libraries, RWL       | Rotterdam, Utrecht |
| gen-4247             | RWL LP ENS002A-GRQ001A 10 Gbit/s               | ens002a-rt01, grq001a-rt04                             | Redwood Libraries, RWL       | Enschede, Groningen |
| gen-4251             | BFU SP TAGGED RMD002A 100 Gbit/s               | rmd002a-rt05                                           | Bluefin University, BFU      | Roermond |
| gen-4252             | NWR LP ASV001A-EHV002A 1 Gbit/s                | ehv002a-rt09, asv001a-rt08                             | Northwind Research, NWR      | Eindhoven, Amstelveen |
| gen-4253             | GFC L2VPN RMD001A-UTR002A 1 Gbit/s             | rmd001a-rt09, utr002a-rt04                             | Greenfield College, GFC      | Roermond, Utrecht |
| gen-4256             | BFH IP ASV002A 100 Gbit/s                      | asv002a-rt07                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4257             | GFC SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt10                                           | Greenfield College, GFC      | Amstelveen |
| gen-4258             | BFH LP ALM002A-EHV001A 1 Gbit/s                | alm002a-rt06, ehv001a-rt12                             | Bluefin Hospital, BFH        | Almere, Eindhoven |
| gen-4259             | BFH SP UNTAGGED RTD002A 1 Gbit/s               | rtd002a-rt08                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4260             | RWL L2VPN AMS001A-EHV001A-MST001A 100 Gbit/s   | ehv001a-rt04, mst001a-rt06, ams001a-rt05               | Redwood Libraries, RWL       | Eindhoven, Maastricht, Amsterdam |
| gen-4263             | RWL L2VPN GOR001A-RMD001A-RMD002A 10 Gbit/s    | rmd002a-rt12, rmd001a-rt04, utr002a-rt10, gor001a-rt12 | Redwood Libraries, RWL       | Roermond, Utrecht, Gorinchem |
| gen-4264             | BFH LP GRQ001A-RMD002A 1 Gbit/s                | grq001a-rt05, rmd002a-rt08                             | Bluefin Hospital, BFH        | Groningen, Roermond |
| gen-4266             | BFH L2VPN ARN001A-EHV002A-MST001A 10 Gbit/s    | ehv002a-rt10, arn001a-rt08, mst001a-rt09               | Bluefin Hospital, BFH        | Eindhoven, Arnhem, Maastricht |
| gen-4267             | RWI SP TAGGED GRQ001A 10 Gbit/s                | grq001a-rt03                                           | Redwood Institute, RWI       | Groningen |
| gen-4269             | SLM L2VPN ALM001A-ARN002A-UTR002A 10 Gbit/s    | utr002a-rt12, arn002a-rt03, alm001a-rt06               | Silverline Museum, SLM       | Utrecht, Arnhem, Almere |
| gen-4270             | BFH SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt09                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-4272             | SLA SP TAGGED MST002A 100 Gbit/s               | mst002a-rt06                                           | Silverline Archives, SLA     | Maastricht |
| gen-4274             | GFC IP MST001A 100 Gbit/s                      | mst001a-rt12                                           | Greenfield College, GFC      | Maastricht |
| gen-4275             | RWL IP UTR002A 10 Gbit/s                       | utr002a-rt08                                           | Redwood Libraries, RWL       | Utrecht |
| gen-4276             | SLM IP MST001A 100 Gbit/s                      | mst001a-rt06                                           | Silverline Museum, SLM       | Maastricht |
| gen-4278             | GFC LP ARN002A-GOR002A 10 Gbit/s               | gor002a-rt12, arn002a-rt06                             | Greenfield College, GFC      | Gorinchem, Arnhem |
| gen-4279             | BFH SP UNTAGGED UTR001A 10 Gbit/s              | utr001a-rt08                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-4281             | RWI SP TAGGED AMS001A 100 Gbit/s               | ams001a-rt08                                           | Redwood Institute, RWI       | Amsterdam |
| gen-4282             | BFH IP UTR001A 1 Gbit/s                        | utr001a-rt11                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-4287             | RWL LP GOR001A-MST001A 100 Gbit/s              | gor001a-rt05, mst001a-rt03                             | Redwood Libraries, RWL       | Gorinchem, Maastricht |
| gen-4293             | BFH SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt04                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-4294             | SLA LP MST002A-UTR001A 100 Gbit/s              | utr001a-rt08, mst002a-rt12                             | Silverline Archives, SLA     | Utrecht, Maastricht |
| gen-4296             | RWI LP MST002A-UTR001A 1 Gbit/s                | utr001a-rt10, mst002a-rt09                             | Redwood Institute, RWI       | Utrecht, Maastricht |
| gen-4300             | BFH SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt08                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-4301             | SLA IP ALM001A 100 Gbit/s                      | alm001a-rt01                                           | Silverline Archives, SLA     | Almere |
| gen-4302             | BFU SP TAGGED EHV002A 100 Gbit/s               | ehv002a-rt02                                           | Bluefin University, BFU      | Eindhoven |
| gen-4306             | NWL L2VPN ALM001A-ALM002A-ASV002A 1 Gbit/s     | asv002a-rt04, alm002a-rt03, grq002a-rt03, alm001a-rt07 | Northwind Labs, NWL          | Amstelveen, Almere, Groningen |
| gen-4307             | SLM IP UTR002A 10 Gbit/s                       | utr002a-rt06                                           | Silverline Museum, SLM       | Utrecht |
| gen-4309             | GFO IP UTR002A 1 Gbit/s                        | utr002a-rt01                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-4311             | RWI LP AMS002A-GRQ001A 100 Gbit/s              | ams002a-rt07, grq001a-rt02                             | Redwood Institute, RWI       | Amsterdam, Groningen |
| gen-4312             | BFU IP ASV002A 100 Gbit/s                      | asv002a-rt11                                           | Bluefin University, BFU      | Amstelveen |
| gen-4313             | BFH IP ARN001A 100 Gbit/s                      | arn001a-rt06                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-4315             | BFU L2VPN ASV002A-GRQ002A-RMD001A 1 Gbit/s     | rmd001a-rt02, grq002a-rt07, asv002a-rt08               | Bluefin University, BFU      | Roermond, Groningen, Amstelveen |
| gen-4316             | GFC L2VPN AMS001A-ARN001A-GOR001A 100 Gbit/s   | ams001a-rt08, arn001a-rt11, gor001a-rt01               | Greenfield College, GFC      | Amsterdam, Arnhem, Gorinchem |
| gen-4317             | NWR LP ARN002A-ENS001A 100 Gbit/s              | ens001a-rt05, arn002a-rt05                             | Northwind Research, NWR      | Enschede, Arnhem |
| gen-4318             | GFO IP ENS002A 1 Gbit/s                        | ens002a-rt02                                           | Greenfield Observatory, GFO  | Enschede |
| gen-4319             | GFO IP UTR001A 10 Gbit/s                       | utr001a-rt06                                           | Greenfield Observatory, GFO  | Utrecht |
| gen-4321             | SLM LP ARN001A-GOR001A 100 Gbit/s              | arn001a-rt05, gor001a-rt09                             | Silverline Museum, SLM       | Arnhem, Gorinchem |
| gen-4322             | RWI IP UTR001A 1 Gbit/s                        | utr001a-rt07                                           | Redwood Institute, RWI       | Utrecht |
| gen-4323             | BFU LP ARN001A-ENS001A 1 Gbit/s                | ens001a-rt09, arn001a-rt04                             | Bluefin University, BFU      | Enschede, Arnhem |
| gen-4324             | RWL IP ENS002A 100 Gbit/s                      | ens002a-rt03                                           | Redwood Libraries, RWL       | Enschede |
| gen-4325             | NWL SP UNTAGGED ASV001A 10 Gbit/s              | asv001a-rt06                                           | Northwind Labs, NWL          | Amstelveen |
| gen-4327             | RWL LP ARN002A-GRQ002A 10 Gbit/s               | grq002a-rt08, arn002a-rt12                             | Redwood Libraries, RWL       | Groningen, Arnhem |
| gen-4329             | SLM L2VPN GRQ002A-UTR001A 100 Gbit/s           | utr001a-rt07, grq002a-rt11                             | Silverline Museum, SLM       | Utrecht, Groningen |
| gen-4330             | GFC LP RTD001A-RTD002A 100 Gbit/s              | rtd002a-rt11, rtd001a-rt04                             | Greenfield College, GFC      | Rotterdam |
| gen-4336             | RWI L2VPN ENS001A-RMD001A-RTD002A 10 Gbit/s    | rmd001a-rt12, rtd002a-rt04, ens001a-rt04               | Redwood Institute, RWI       | Roermond, Rotterdam, Enschede |
| gen-4339             | GFC IP UTR002A 100 Gbit/s                      | utr002a-rt09                                           | Greenfield College, GFC      | Utrecht |
| gen-4340             | GFO L2VPN ARN002A-ASV001A-EHV001A 10 Gbit/s    | asv001a-rt09, arn002a-rt09, ehv001a-rt06               | Greenfield Observatory, GFO  | Amstelveen, Arnhem, Eindhoven |
| gen-4341             | RWL LP ALM001A-ENS001A 1 Gbit/s                | alm001a-rt07, ens001a-rt09                             | Redwood Libraries, RWL       | Almere, Enschede |
| gen-4343             | RWI SP TAGGED ALM001A 10 Gbit/s                | alm001a-rt10                                           | Redwood Institute, RWI       | Almere |
| gen-4344             | NWL SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt03                                           | Northwind Labs, NWL          | Roermond |
| gen-4345             | RWI LP RMD001A-RMD002A 100 Gbit/s              | rmd002a-rt12, rmd001a-rt06                             | Redwood Institute, RWI       | Roermond |
| gen-4346             | RWI L2VPN ALM002A-ARN002A 1 Gbit/s             | alm002a-rt08, arn002a-rt12                             | Redwood Institute, RWI       | Almere, Arnhem |
| gen-4347             | SLA SP UNTAGGED UTR001A 10 Gbit/s              | utr001a-rt09                                           | Silverline Archives, SLA     | Utrecht |
| gen-4349             | GFC IP AMS001A 100 Gbit/s                      | ams001a-rt06                                           | Greenfield College, GFC      | Amsterdam |
| gen-4351             | GFC LP MST002A-UTR002A 10 Gbit/s               | utr002a-rt04, mst002a-rt10                             | Greenfield College, GFC      | Utrecht, Maastricht |
| gen-4353             | SLM SP TAGGED GOR001A 10 Gbit/s                | gor001a-rt04                                           | Silverline Museum, SLM       | Gorinchem |
| gen-4356             | BFU LP ENS002A-GOR002A 100 Gbit/s              | gor002a-rt12, ens002a-rt11                             | Bluefin University, BFU      | Gorinchem, Enschede |
| gen-4357             | NWL LP ASV002A-RMD002A 1 Gbit/s                | rmd002a-rt03, asv002a-rt09                             | Northwind Labs, NWL          | Roermond, Amstelveen |
| gen-4358             | RWI SP TAGGED ARN002A 100 Gbit/s               | arn002a-rt02                                           | Redwood Institute, RWI       | Arnhem |
| gen-4359             | RWL L2VPN EHV001A-GOR001A 100 Gbit/s           | ehv001a-rt06, gor001a-rt04                             | Redwood Libraries, RWL       | Eindhoven, Gorinchem |
| gen-4363             | SLM LP ASV001A-MST001A 10 Gbit/s               | asv001a-rt05, mst001a-rt02                             | Silverline Museum, SLM       | Amstelveen, Maastricht |
| gen-4365             | GFC IP ASV001A 1 Gbit/s                        | asv001a-rt10                                           | Greenfield College, GFC      | Amstelveen |
| gen-4367             | BFH LP GOR002A-MST002A 1 Gbit/s                | mst002a-rt08, gor002a-rt07                             | Bluefin Hospital, BFH        | Maastricht, Gorinchem |
| gen-4368             | GFO SP TAGGED ASV001A 10 Gbit/s                | asv001a-rt10                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-4369             | SLM L2VPN AMS001A-GOR001A-GOR002A 10 Gbit/s    | ams001a-rt05, gor002a-rt04, gor001a-rt10               | Silverline Museum, SLM       | Amsterdam, Gorinchem |
| gen-4370             | NWL L2VPN ALM002A-ARN002A-EHV001A 10 Gbit/s    | ehv001a-rt09, alm002a-rt08, rmd001a-rt06, arn002a-rt10 | Northwind Labs, NWL          | Eindhoven, Almere, Roermond, Arnhem |
| gen-4371             | SLM SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt02                                           | Silverline Museum, SLM       | Groningen |
| gen-4373             | GFO L2VPN AMS002A-RMD002A 100 Gbit/s           | rmd002a-rt01, ams002a-rt02                             | Greenfield Observatory, GFO  | Roermond, Amsterdam |
| gen-4374             | GFO IP RMD002A 10 Gbit/s                       | rmd002a-rt01                                           | Greenfield Observatory, GFO  | Roermond |
| gen-4376             | RWI SP UNTAGGED RMD001A 10 Gbit/s              | rmd001a-rt02                                           | Redwood Institute, RWI       | Roermond |
| gen-4379             | GFO SP TAGGED ENS001A 1 Gbit/s                 | ens001a-rt04                                           | Greenfield Observatory, GFO  | Enschede |
| gen-4383             | BFH IP ALM002A 10 Gbit/s                       | alm002a-rt09                                           | Bluefin Hospital, BFH        | Almere |
| gen-4385             | RWI SP TAGGED ENS001A 10 Gbit/s                | ens001a-rt05                                           | Redwood Institute, RWI       | Enschede |
| gen-4386             | RWL L2VPN ALM001A-ARN001A 1 Gbit/s             | alm001a-rt08, arn001a-rt08                             | Redwood Libraries, RWL       | Almere, Arnhem |
| gen-4387             | GFO IP AMS001A 10 Gbit/s                       | ams001a-rt04                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-4388             | GFC L2VPN ARN001A-ENS002A-RMD001A 100 Gbit/s   | arn001a-rt04, utr002a-rt08, ens002a-rt03, rmd001a-rt05 | Greenfield College, GFC      | Arnhem, Utrecht, Enschede, Roermond |
| gen-4389             | GFC LP ALM001A-ARN001A 100 Gbit/s              | alm001a-rt06, arn001a-rt08                             | Greenfield College, GFC      | Almere, Arnhem |
| gen-4390             | RWI L2VPN AMS002A-ARN002A-EHV001A 1 Gbit/s     | ams002a-rt08, ehv001a-rt09, arn002a-rt08               | Redwood Institute, RWI       | Amsterdam, Eindhoven, Arnhem |
| gen-4391             | NWR SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt08                                           | Northwind Research, NWR      | Maastricht |
| gen-4393             | NWR IP GRQ001A 10 Gbit/s                       | grq001a-rt03                                           | Northwind Research, NWR      | Groningen |
| gen-4394             | NWL LP ARN002A-ENS001A 10 Gbit/s               | ens001a-rt09, arn002a-rt03                             | Northwind Labs, NWL          | Enschede, Arnhem |
| gen-4396             | BFU L2VPN ALM001A-MST001A-MST002A 10 Gbit/s    | mst001a-rt04, mst002a-rt04, rmd001a-rt02, alm001a-rt08 | Bluefin University, BFU      | Maastricht, Roermond, Almere |
| gen-4401             | BFU IP ASV002A 10 Gbit/s                       | asv002a-rt06                                           | Bluefin University, BFU      | Amstelveen |
| gen-4402             | NWR IP EHV002A 100 Gbit/s                      | ehv002a-rt08                                           | Northwind Research, NWR      | Eindhoven |
| gen-4405             | SLA SP TAGGED GOR002A 1 Gbit/s                 | gor002a-rt07                                           | Silverline Archives, SLA     | Gorinchem |
| gen-4407             | GFC IP GRQ001A 10 Gbit/s                       | grq001a-rt07                                           | Greenfield College, GFC      | Groningen |
| gen-4410             | GFO L2VPN AMS001A-ARN002A-ASV002A 100 Gbit/s   | arn002a-rt10, asv002a-rt07, ams001a-rt09               | Greenfield Observatory, GFO  | Arnhem, Amstelveen, Amsterdam |
| gen-4411             | RWI IP AMS002A 10 Gbit/s                       | ams002a-rt01                                           | Redwood Institute, RWI       | Amsterdam |
| gen-4412             | SLA SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt09                                           | Silverline Archives, SLA     | Almere |
| gen-4413             | BFH IP RTD001A 100 Gbit/s                      | rtd001a-rt10                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4414             | RWI IP ENS001A 1 Gbit/s                        | ens001a-rt02                                           | Redwood Institute, RWI       | Enschede |
| gen-4421             | GFO L2VPN ENS001A-MST001A-RTD001A 1 Gbit/s     | mst001a-rt04, rtd001a-rt09, ens001a-rt10               | Greenfield Observatory, GFO  | Maastricht, Rotterdam, Enschede |
| gen-4426             | SLA SP UNTAGGED AMS001A 1 Gbit/s               | ams001a-rt02                                           | Silverline Archives, SLA     | Amsterdam |
| gen-4429             | BFH LP EHV001A-MST002A 1 Gbit/s                | ehv001a-rt07, mst002a-rt06                             | Bluefin Hospital, BFH        | Eindhoven, Maastricht |
| gen-4431             | GFO L2VPN RMD002A-UTR001A-UTR002A 1 Gbit/s     | utr001a-rt11, rmd002a-rt12, utr002a-rt12               | Greenfield Observatory, GFO  | Utrecht, Roermond |
| gen-4432             | NWL SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt11                                           | Northwind Labs, NWL          | Arnhem |
| gen-4434             | NWL IP GOR001A 1 Gbit/s                        | gor001a-rt05                                           | Northwind Labs, NWL          | Gorinchem |
| gen-4436             | BFU IP MST002A 10 Gbit/s                       | mst002a-rt08                                           | Bluefin University, BFU      | Maastricht |
| gen-4439             | RWI SP TAGGED ARN002A 100 Gbit/s               | arn002a-rt12                                           | Redwood Institute, RWI       | Arnhem |
| gen-4441             | SLA IP UTR001A 1 Gbit/s                        | utr001a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-4445             | SLM SP TAGGED MST002A 10 Gbit/s                | mst002a-rt06                                           | Silverline Museum, SLM       | Maastricht |
| gen-4446             | RWI L2VPN ARN001A-MST001A 1 Gbit/s             | arn001a-rt05, mst001a-rt08                             | Redwood Institute, RWI       | Arnhem, Maastricht |
| gen-4450             | NWR SP TAGGED ENS002A 1 Gbit/s                 | ens002a-rt07                                           | Northwind Research, NWR      | Enschede |
| gen-4452             | GFC SP TAGGED ALM002A 100 Gbit/s               | alm002a-rt04                                           | Greenfield College, GFC      | Almere |
| gen-4454             | BFU LP ENS002A-GRQ002A 1 Gbit/s                | ens002a-rt05, grq002a-rt09                             | Bluefin University, BFU      | Enschede, Groningen |
| gen-4455             | NWL IP GRQ002A 100 Gbit/s                      | grq002a-rt02                                           | Northwind Labs, NWL          | Groningen |
| gen-4457             | SLM SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt09                                           | Silverline Museum, SLM       | Amstelveen |
| gen-4458             | NWR SP TAGGED RMD002A 1 Gbit/s                 | rmd002a-rt02                                           | Northwind Research, NWR      | Roermond |
| gen-4459             | NWR IP ARN002A 10 Gbit/s                       | arn002a-rt07                                           | Northwind Research, NWR      | Arnhem |
| gen-4461             | BFU IP EHV001A 10 Gbit/s                       | ehv001a-rt04                                           | Bluefin University, BFU      | Eindhoven |
| gen-4464             | BFU IP EHV001A 10 Gbit/s                       | ehv001a-rt10                                           | Bluefin University, BFU      | Eindhoven |
| gen-4469             | SLM L2VPN ASV001A-GOR001A-MST001A 10 Gbit/s    | gor001a-rt05, utr002a-rt11, asv001a-rt06, mst001a-rt04 | Silverline Museum, SLM       | Gorinchem, Utrecht, Amstelveen, Maastricht |
| gen-4470             | NWR SP TAGGED ASV001A 1 Gbit/s                 | asv001a-rt12                                           | Northwind Research, NWR      | Amstelveen |
| gen-4471             | RWI IP AMS001A 10 Gbit/s                       | ams001a-rt09                                           | Redwood Institute, RWI       | Amsterdam |
| gen-4472             | SLM IP GOR002A 1 Gbit/s                        | gor002a-rt05                                           | Silverline Museum, SLM       | Gorinchem |
| gen-4474             | SLA IP ARN002A 1 Gbit/s                        | arn002a-rt06                                           | Silverline Archives, SLA     | Arnhem |
| gen-4475             | GFO IP RMD001A 1 Gbit/s                        | rmd001a-rt10                                           | Greenfield Observatory, GFO  | Roermond |
| gen-4476             | GFO LP ARN002A-ASV001A 100 Gbit/s              | arn002a-rt02, asv001a-rt10                             | Greenfield Observatory, GFO  | Arnhem, Amstelveen |
| gen-4477             | GFO IP ASV002A 10 Gbit/s                       | asv002a-rt06                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-4479             | GFC LP ALM001A-ENS002A 10 Gbit/s               | ens002a-rt01, alm001a-rt01                             | Greenfield College, GFC      | Enschede, Almere |
| gen-4481             | NWL L2VPN EHV002A-RMD002A 1 Gbit/s             | ehv002a-rt09, rmd002a-rt12                             | Northwind Labs, NWL          | Eindhoven, Roermond |
| gen-4484             | SLA LP UTR001A-UTR002A 1 Gbit/s                | utr002a-rt12, utr001a-rt09                             | Silverline Archives, SLA     | Utrecht |
| gen-4485             | RWI IP GOR002A 100 Gbit/s                      | gor002a-rt07                                           | Redwood Institute, RWI       | Gorinchem |
| gen-4486             | GFC IP RTD002A 10 Gbit/s                       | rtd002a-rt05                                           | Greenfield College, GFC      | Rotterdam |
| gen-4491             | GFC L2VPN ALM001A-AMS002A-RTD002A 10 Gbit/s    | rtd002a-rt03, alm001a-rt06, ams002a-rt07               | Greenfield College, GFC      | Rotterdam, Almere, Amsterdam |
| gen-4492             | GFC L2VPN EHV001A-GRQ001A 100 Gbit/s           | ehv001a-rt10, grq001a-rt09                             | Greenfield College, GFC      | Eindhoven, Groningen |
| gen-4494             | BFU SP TAGGED UTR002A 10 Gbit/s                | utr002a-rt07                                           | Bluefin University, BFU      | Utrecht |
| gen-4495             | NWR LP ARN001A-MST001A 10 Gbit/s               | mst001a-rt10, arn001a-rt11                             | Northwind Research, NWR      | Maastricht, Arnhem |
| gen-4497             | SLM LP ARN002A-UTR001A 1 Gbit/s                | arn002a-rt01, utr001a-rt07                             | Silverline Museum, SLM       | Arnhem, Utrecht |
| gen-4498             | SLM SP TAGGED ASV002A 10 Gbit/s                | asv002a-rt06                                           | Silverline Museum, SLM       | Amstelveen |
| gen-4500             | GFO SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt02                                           | Greenfield Observatory, GFO  | Groningen |
| gen-4502             | RWI L2VPN AMS002A-ARN002A-GOR001A 100 Gbit/s   | gor002a-rt11, ams002a-rt04, gor001a-rt06, arn002a-rt04 | Redwood Institute, RWI       | Gorinchem, Amsterdam, Arnhem |
| gen-4504             | SLM LP GRQ001A-MST002A 100 Gbit/s              | mst002a-rt01, grq001a-rt01                             | Silverline Museum, SLM       | Maastricht, Groningen |
| gen-4505             | GFO IP RTD002A 1 Gbit/s                        | rtd002a-rt10                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-4506             | BFU IP RTD002A 10 Gbit/s                       | rtd002a-rt12                                           | Bluefin University, BFU      | Rotterdam |
| gen-4515             | NWR IP ALM001A 1 Gbit/s                        | alm001a-rt07                                           | Northwind Research, NWR      | Almere |
| gen-4516             | RWL IP UTR002A 1 Gbit/s                        | utr002a-rt10                                           | Redwood Libraries, RWL       | Utrecht |
| gen-4518             | BFH L2VPN ASV001A-EHV002A 100 Gbit/s           | asv001a-rt09, asv001a-rt07, ehv002a-rt09               | Bluefin Hospital, BFH        | Amstelveen, Eindhoven |
| gen-4519             | RWL IP GRQ002A 100 Gbit/s                      | grq002a-rt08                                           | Redwood Libraries, RWL       | Groningen |
| gen-4520             | SLM LP ALM002A-ARN001A 100 Gbit/s              | arn001a-rt02, alm002a-rt07                             | Silverline Museum, SLM       | Arnhem, Almere |
| gen-4522             | NWR L2VPN ASV001A-EHV002A-MST001A 100 Gbit/s   | ehv002a-rt03, mst001a-rt01, asv001a-rt10               | Northwind Research, NWR      | Eindhoven, Maastricht, Amstelveen |
| gen-4524             | BFU L2VPN ASV001A-ASV002A-EHV001A 1 Gbit/s     | asv002a-rt06, asv001a-rt05, ehv001a-rt04               | Bluefin University, BFU      | Amstelveen, Eindhoven |
| gen-4526             | GFC SP UNTAGGED UTR001A 1 Gbit/s               | utr001a-rt01                                           | Greenfield College, GFC      | Utrecht |
| gen-4527             | BFU L2VPN ALM001A-GRQ001A 100 Gbit/s           | alm001a-rt05, grq001a-rt10                             | Bluefin University, BFU      | Almere, Groningen |
| gen-4529             | GFC LP GRQ002A-RMD001A 1 Gbit/s                | grq002a-rt11, rmd001a-rt02                             | Greenfield College, GFC      | Groningen, Roermond |
| gen-4530             | RWI LP RMD002A-UTR001A 10 Gbit/s               | rmd002a-rt03, utr001a-rt11                             | Redwood Institute, RWI       | Roermond, Utrecht |
| gen-4532             | NWL L2VPN EHV001A-GOR001A 1 Gbit/s             | gor001a-rt06, ehv001a-rt06                             | Northwind Labs, NWL          | Gorinchem, Eindhoven |
| gen-4533             | RWL IP UTR002A 1 Gbit/s                        | utr002a-rt03                                           | Redwood Libraries, RWL       | Utrecht |
| gen-4534             | GFC SP UNTAGGED UTR002A 10 Gbit/s              | utr002a-rt11                                           | Greenfield College, GFC      | Utrecht |
| gen-4535             | GFC L2VPN EHV001A-EHV002A-GOR001A 100 Gbit/s   | ehv002a-rt10, gor002a-rt11, ehv001a-rt08, gor001a-rt01 | Greenfield College, GFC      | Eindhoven, Gorinchem |
| gen-4536             | BFU SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt12                                           | Bluefin University, BFU      | Arnhem |
| gen-4538             | RWI LP RMD002A-RMD002A 1 Gbit/s                | rmd002a-rt12, rmd002a-rt06                             | Redwood Institute, RWI       | Roermond |
| gen-4539             | SLA SP UNTAGGED AMS002A 100 Gbit/s             | ams002a-rt03                                           | Silverline Archives, SLA     | Amsterdam |
| gen-4540             | SLA LP GOR001A-UTR001A 100 Gbit/s              | utr001a-rt12, gor001a-rt07                             | Silverline Archives, SLA     | Utrecht, Gorinchem |
| gen-4541             | GFO LP ASV001A-ASV001A 1 Gbit/s                | asv001a-rt11, asv001a-rt04                             | Greenfield Observatory, GFO  | Amstelveen |
| gen-4547             | NWR LP ALM001A-MST001A 100 Gbit/s              | alm001a-rt03, mst001a-rt04                             | Northwind Research, NWR      | Almere, Maastricht |
| gen-4550             | SLM IP ARN002A 100 Gbit/s                      | arn002a-rt10                                           | Silverline Museum, SLM       | Arnhem |
| gen-4551             | SLM IP MST002A 1 Gbit/s                        | mst002a-rt08                                           | Silverline Museum, SLM       | Maastricht |
| gen-4554             | NWR L2VPN EHV002A-GOR002A 10 Gbit/s            | ehv002a-rt03, gor002a-rt10                             | Northwind Research, NWR      | Eindhoven, Gorinchem |
| gen-4555             | BFH IP ASV001A 1 Gbit/s                        | asv001a-rt03                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4556             | GFC L2VPN ARN002A-EHV002A-ENS001A 1 Gbit/s     | ehv002a-rt08, arn002a-rt04, ens001a-rt10, ens001a-rt12 | Greenfield College, GFC      | Eindhoven, Arnhem, Enschede |
| gen-4558             | GFO SP UNTAGGED EHV001A 10 Gbit/s              | ehv001a-rt11                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-4559             | BFH LP ASV002A-RTD001A 10 Gbit/s               | asv002a-rt03, rtd001a-rt04                             | Bluefin Hospital, BFH        | Amstelveen, Rotterdam |
| gen-4561             | SLM SP TAGGED ARN002A 10 Gbit/s                | arn002a-rt09                                           | Silverline Museum, SLM       | Arnhem |
| gen-4567             | GFC SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt01                                           | Greenfield College, GFC      | Maastricht |
| gen-4570             | BFU L2VPN ARN002A-ASV001A 10 Gbit/s            | arn002a-rt02, asv001a-rt09                             | Bluefin University, BFU      | Arnhem, Amstelveen |
| gen-4571             | NWL IP MST002A 100 Gbit/s                      | mst002a-rt01                                           | Northwind Labs, NWL          | Maastricht |
| gen-4578             | BFU SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt02                                           | Bluefin University, BFU      | Amstelveen |
| gen-4580             | RWL LP ARN001A-MST001A 100 Gbit/s              | mst001a-rt11, arn001a-rt05                             | Redwood Libraries, RWL       | Maastricht, Arnhem |
| gen-4581             | RWL LP GOR001A-RTD001A 1 Gbit/s                | rtd001a-rt10, gor001a-rt10                             | Redwood Libraries, RWL       | Rotterdam, Gorinchem |
| gen-4583             | SLA L2VPN ALM001A-GRQ001A-UTR002A 1 Gbit/s     | grq001a-rt06, alm001a-rt03, utr002a-rt04               | Silverline Archives, SLA     | Groningen, Almere, Utrecht |
| gen-4584             | NWL IP ASV002A 100 Gbit/s                      | asv002a-rt12                                           | Northwind Labs, NWL          | Amstelveen |
| gen-4585             | SLM SP TAGGED GOR002A 1 Gbit/s                 | gor002a-rt11                                           | Silverline Museum, SLM       | Gorinchem |
| gen-4586             | NWL LP ARN002A-ENS001A 1 Gbit/s                | arn002a-rt10, ens001a-rt11                             | Northwind Labs, NWL          | Arnhem, Enschede |
| gen-4590             | BFH IP ASV002A 100 Gbit/s                      | asv002a-rt11                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4591             | GFO SP TAGGED RMD002A 10 Gbit/s                | rmd002a-rt01                                           | Greenfield Observatory, GFO  | Roermond |
| gen-4593             | BFH LP ARN002A-GOR001A 1 Gbit/s                | gor001a-rt11, arn002a-rt09                             | Bluefin Hospital, BFH        | Gorinchem, Arnhem |
| gen-4594             | SLM SP UNTAGGED UTR002A 1 Gbit/s               | utr002a-rt07                                           | Silverline Museum, SLM       | Utrecht |
| gen-4597             | BFH IP ARN001A 10 Gbit/s                       | arn001a-rt12                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-4600             | BFH SP UNTAGGED MST002A 100 Gbit/s             | mst002a-rt10                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-4602             | RWL LP RMD001A-UTR001A 100 Gbit/s              | utr001a-rt05, rmd001a-rt03                             | Redwood Libraries, RWL       | Utrecht, Roermond |
| gen-4603             | GFC L2VPN ENS002A-UTR002A 1 Gbit/s             | utr002a-rt03, ens002a-rt03                             | Greenfield College, GFC      | Utrecht, Enschede |
| gen-4605             | RWL SP TAGGED AMS002A 100 Gbit/s               | ams002a-rt12                                           | Redwood Libraries, RWL       | Amsterdam |
| gen-4607             | GFO LP ARN001A-GRQ001A 1 Gbit/s                | arn001a-rt07, grq001a-rt03                             | Greenfield Observatory, GFO  | Arnhem, Groningen |
| gen-4608             | GFC LP GOR001A-GOR001A 10 Gbit/s               | gor001a-rt09, gor001a-rt08                             | Greenfield College, GFC      | Gorinchem |
| gen-4610             | RWL IP GRQ002A 10 Gbit/s                       | grq002a-rt05                                           | Redwood Libraries, RWL       | Groningen |
| gen-4613             | SLM LP ALM001A-UTR002A 1 Gbit/s                | utr002a-rt09, alm001a-rt04                             | Silverline Museum, SLM       | Utrecht, Almere |
| gen-4614             | GFO IP RMD002A 100 Gbit/s                      | rmd002a-rt02                                           | Greenfield Observatory, GFO  | Roermond |
| gen-4615             | GFC IP MST002A 1 Gbit/s                        | mst002a-rt03                                           | Greenfield College, GFC      | Maastricht |
| gen-4616             | BFU IP RTD002A 10 Gbit/s                       | rtd002a-rt07                                           | Bluefin University, BFU      | Rotterdam |
| gen-4617             | NWR LP ASV001A-GRQ001A 10 Gbit/s               | grq001a-rt08, asv001a-rt05                             | Northwind Research, NWR      | Groningen, Amstelveen |
| gen-4618             | BFH L2VPN ALM001A-ALM002A-GRQ001A 1 Gbit/s     | grq001a-rt08, alm001a-rt11, grq001a-rt05, alm002a-rt04 | Bluefin Hospital, BFH        | Groningen, Almere |
| gen-4620             | RWI LP GOR002A-MST002A 100 Gbit/s              | mst002a-rt08, gor002a-rt07                             | Redwood Institute, RWI       | Maastricht, Gorinchem |
| gen-4624             | NWR SP TAGGED GOR002A 1 Gbit/s                 | gor002a-rt01                                           | Northwind Research, NWR      | Gorinchem |
| gen-4625             | GFO SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt03                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-4626             | NWR LP ALM001A-ENS002A 100 Gbit/s              | alm001a-rt08, ens002a-rt08                             | Northwind Research, NWR      | Almere, Enschede |
| gen-4628             | BFH SP TAGGED RTD001A 100 Gbit/s               | rtd001a-rt04                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4630             | GFO SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt04                                           | Greenfield Observatory, GFO  | Enschede |
| gen-4631             | SLM IP ARN002A 1 Gbit/s                        | arn002a-rt03                                           | Silverline Museum, SLM       | Arnhem |
| gen-4632             | GFO SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt12                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-4634             | SLM IP MST002A 10 Gbit/s                       | mst002a-rt12                                           | Silverline Museum, SLM       | Maastricht |
| gen-4635             | GFO LP ASV002A-UTR002A 100 Gbit/s              | asv002a-rt07, utr002a-rt06                             | Greenfield Observatory, GFO  | Amstelveen, Utrecht |
| gen-4637             | GFC IP AMS001A 10 Gbit/s                       | ams001a-rt03                                           | Greenfield College, GFC      | Amsterdam |
| gen-4638             | RWL IP ENS001A 10 Gbit/s                       | ens001a-rt08                                           | Redwood Libraries, RWL       | Enschede |
| gen-4639             | RWI IP RMD001A 100 Gbit/s                      | rmd001a-rt02                                           | Redwood Institute, RWI       | Roermond |
| gen-4640             | RWI IP GOR001A 100 Gbit/s                      | gor001a-rt03                                           | Redwood Institute, RWI       | Gorinchem |
| gen-4644             | GFO SP UNTAGGED AMS002A 10 Gbit/s              | ams002a-rt07                                           | Greenfield Observatory, GFO  | Amsterdam |
| gen-4645             | RWI L2VPN MST001A-RTD001A 1 Gbit/s             | rtd001a-rt05, mst001a-rt06                             | Redwood Institute, RWI       | Rotterdam, Maastricht |
| gen-4646             | SLM IP AMS001A 1 Gbit/s                        | ams001a-rt05                                           | Silverline Museum, SLM       | Amsterdam |
| gen-4647             | RWI IP ARN002A 100 Gbit/s                      | arn002a-rt09                                           | Redwood Institute, RWI       | Arnhem |
| gen-4648             | SLM SP TAGGED GRQ002A 100 Gbit/s               | grq002a-rt11                                           | Silverline Museum, SLM       | Groningen |
| gen-4650             | SLM SP UNTAGGED GRQ002A 100 Gbit/s             | grq002a-rt09                                           | Silverline Museum, SLM       | Groningen |
| gen-4651             | RWL IP ARN002A 10 Gbit/s                       | arn002a-rt06                                           | Redwood Libraries, RWL       | Arnhem |
| gen-4656             | GFO LP ALM002A-UTR002A 100 Gbit/s              | alm002a-rt11, utr002a-rt01                             | Greenfield Observatory, GFO  | Almere, Utrecht |
| gen-4657             | NWL L2VPN ARN002A 1 Gbit/s                     | arn002a-rt09, arn002a-rt03                             | Northwind Labs, NWL          | Arnhem |
| gen-4658             | SLM L2VPN ALM002A-ASV001A-GOR002A 10 Gbit/s    | asv001a-rt03, alm002a-rt03, gor002a-rt01               | Silverline Museum, SLM       | Amstelveen, Almere, Gorinchem |
| gen-4662             | SLA LP ARN001A-GRQ001A 1 Gbit/s                | arn001a-rt06, grq001a-rt10                             | Silverline Archives, SLA     | Arnhem, Groningen |
| gen-4664             | GFC IP ARN002A 1 Gbit/s                        | arn002a-rt05                                           | Greenfield College, GFC      | Arnhem |
| gen-4667             | GFO IP ENS001A 1 Gbit/s                        | ens001a-rt02                                           | Greenfield Observatory, GFO  | Enschede |
| gen-4668             | SLA L2VPN ALM001A-GRQ002A 100 Gbit/s           | alm001a-rt09, grq002a-rt03                             | Silverline Archives, SLA     | Almere, Groningen |
| gen-4669             | BFH IP MST002A 1 Gbit/s                        | mst002a-rt10                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-4670             | RWL LP AMS001A-RMD002A 100 Gbit/s              | ams001a-rt02, rmd002a-rt01                             | Redwood Libraries, RWL       | Amsterdam, Roermond |
| gen-4671             | GFO SP UNTAGGED GOR002A 1 Gbit/s               | gor002a-rt04                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-4673             | SLA IP MST002A 100 Gbit/s                      | mst002a-rt09                                           | Silverline Archives, SLA     | Maastricht |
| gen-4674             | NWL IP ARN002A 100 Gbit/s                      | arn002a-rt01                                           | Northwind Labs, NWL          | Arnhem |
| gen-4675             | GFO L2VPN EHV001A-RTD001A 100 Gbit/s           | rtd001a-rt11, ehv001a-rt09                             | Greenfield Observatory, GFO  | Rotterdam, Eindhoven |
| gen-4677             | GFO LP ALM001A-GRQ001A 10 Gbit/s               | alm001a-rt12, grq001a-rt02                             | Greenfield Observatory, GFO  | Almere, Groningen |
| gen-4679             | BFU L2VPN ALM001A-EHV001A-GOR002A 100 Gbit/s   | ehv001a-rt07, alm001a-rt01, gor002a-rt08               | Bluefin University, BFU      | Eindhoven, Almere, Gorinchem |
| gen-4681             | NWL LP ARN001A-ARN002A 100 Gbit/s              | arn001a-rt08, arn002a-rt08                             | Northwind Labs, NWL          | Arnhem |
| gen-4682             | GFC SP TAGGED RTD001A 1 Gbit/s                 | rtd001a-rt06                                           | Greenfield College, GFC      | Rotterdam |
| gen-4690             | RWL SP UNTAGGED ENS001A 100 Gbit/s             | ens001a-rt06                                           | Redwood Libraries, RWL       | Enschede |
| gen-4691             | GFO LP ASV001A-MST001A 1 Gbit/s                | mst001a-rt04, asv001a-rt04                             | Greenfield Observatory, GFO  | Maastricht, Amstelveen |
| gen-4693             | GFO LP GRQ002A-RMD001A 10 Gbit/s               | rmd001a-rt09, grq002a-rt10                             | Greenfield Observatory, GFO  | Roermond, Groningen |
| gen-4694             | BFH SP UNTAGGED RMD001A 1 Gbit/s               | rmd001a-rt05                                           | Bluefin Hospital, BFH        | Roermond |
| gen-4699             | BFU IP MST001A 100 Gbit/s                      | mst001a-rt10                                           | Bluefin University, BFU      | Maastricht |
| gen-4700             | GFC L2VPN ARN001A-ARN002A-UTR002A 1 Gbit/s     | arn002a-rt12, arn001a-rt10, utr002a-rt09               | Greenfield College, GFC      | Arnhem, Utrecht |
| gen-4701             | NWR IP EHV002A 10 Gbit/s                       | ehv002a-rt09                                           | Northwind Research, NWR      | Eindhoven |
| gen-4703             | BFU L2VPN EHV001A-GOR002A-GRQ002A 10 Gbit/s    | grq002a-rt08, gor002a-rt05, ehv001a-rt04               | Bluefin University, BFU      | Groningen, Gorinchem, Eindhoven |
| gen-4704             | NWL IP EHV001A 100 Gbit/s                      | ehv001a-rt12                                           | Northwind Labs, NWL          | Eindhoven |
| gen-4705             | GFC SP TAGGED GOR001A 1 Gbit/s                 | gor001a-rt01                                           | Greenfield College, GFC      | Gorinchem |
| gen-4707             | GFC L2VPN ASV002A-ENS002A-RMD001A 100 Gbit/s   | rmd001a-rt08, asv002a-rt02, ens002a-rt07               | Greenfield College, GFC      | Roermond, Amstelveen, Enschede |
| gen-4708             | NWL SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt10                                           | Northwind Labs, NWL          | Maastricht |
| gen-4709             | RWL SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt04                                           | Redwood Libraries, RWL       | Arnhem |
| gen-4710             | GFO IP ARN001A 100 Gbit/s                      | arn001a-rt11                                           | Greenfield Observatory, GFO  | Arnhem |
| gen-4713             | GFC IP GRQ002A 100 Gbit/s                      | grq002a-rt07                                           | Greenfield College, GFC      | Groningen |
| gen-4715             | SLM L2VPN ASV002A-GOR002A-MST002A 10 Gbit/s    | gor002a-rt12, gor002a-rt07, mst002a-rt04, asv002a-rt02 | Silverline Museum, SLM       | Gorinchem, Maastricht, Amstelveen |
| gen-4718             | NWL L2VPN ARN002A-RMD002A 1 Gbit/s             | arn002a-rt12, rmd002a-rt05                             | Northwind Labs, NWL          | Arnhem, Roermond |
| gen-4722             | GFC L2VPN AMS001A-EHV002A-ENS002A 1 Gbit/s     | ehv002a-rt07, ams001a-rt08, ens002a-rt10               | Greenfield College, GFC      | Eindhoven, Amsterdam, Enschede |
| gen-4723             | GFO IP MST001A 10 Gbit/s                       | mst001a-rt12                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-4724             | SLA IP MST001A 10 Gbit/s                       | mst001a-rt11                                           | Silverline Archives, SLA     | Maastricht |
| gen-4725             | RWL LP GOR002A-MST001A 10 Gbit/s               | gor002a-rt02, mst001a-rt10                             | Redwood Libraries, RWL       | Gorinchem, Maastricht |
| gen-4726             | NWL IP RMD001A 100 Gbit/s                      | rmd001a-rt06                                           | Northwind Labs, NWL          | Roermond |
| gen-4729             | NWR L2VPN ARN002A-EHV002A-GOR002A 10 Gbit/s    | gor002a-rt05, ehv002a-rt10, arn002a-rt02               | Northwind Research, NWR      | Gorinchem, Eindhoven, Arnhem |
| gen-4731             | GFC LP ALM001A-ALM001A 1 Gbit/s                | alm001a-rt02, alm001a-rt08                             | Greenfield College, GFC      | Almere |
| gen-4734             | SLM IP ALM001A 10 Gbit/s                       | alm001a-rt10                                           | Silverline Museum, SLM       | Almere |
| gen-4736             | BFU SP TAGGED RMD001A 100 Gbit/s               | rmd001a-rt05                                           | Bluefin University, BFU      | Roermond |
| gen-4737             | SLA L2VPN MST002A 10 Gbit/s                    | mst002a-rt03, mst002a-rt10                             | Silverline Archives, SLA     | Maastricht |
| gen-4738             | NWR SP UNTAGGED RMD001A 1 Gbit/s               | rmd001a-rt04                                           | Northwind Research, NWR      | Roermond |
| gen-4741             | SLM SP UNTAGGED UTR001A 10 Gbit/s              | utr001a-rt12                                           | Silverline Museum, SLM       | Utrecht |
| gen-4743             | NWL SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt01                                           | Northwind Labs, NWL          | Gorinchem |
| gen-4744             | RWL LP ARN002A-RMD001A 1 Gbit/s                | arn002a-rt10, rmd001a-rt05                             | Redwood Libraries, RWL       | Arnhem, Roermond |
| gen-4745             | RWI L2VPN ENS001A-UTR001A 10 Gbit/s            | ens001a-rt06, utr001a-rt06                             | Redwood Institute, RWI       | Enschede, Utrecht |
| gen-4746             | BFU SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt06                                           | Bluefin University, BFU      | Amstelveen |
| gen-4748             | RWI SP TAGGED RMD001A 1 Gbit/s                 | rmd001a-rt06                                           | Redwood Institute, RWI       | Roermond |
| gen-4750             | SLA IP ASV002A 1 Gbit/s                        | asv002a-rt01                                           | Silverline Archives, SLA     | Amstelveen |
| gen-4753             | NWR LP ENS001A-GRQ002A 10 Gbit/s               | grq002a-rt05, ens001a-rt04                             | Northwind Research, NWR      | Groningen, Enschede |
| gen-4754             | NWL SP TAGGED RMD001A 10 Gbit/s                | rmd001a-rt06                                           | Northwind Labs, NWL          | Roermond |
| gen-4755             | RWL L2VPN EHV002A-MST002A 100 Gbit/s           | mst002a-rt06, ehv002a-rt03                             | Redwood Libraries, RWL       | Maastricht, Eindhoven |
| gen-4756             | RWI IP GRQ002A 100 Gbit/s                      | grq002a-rt07                                           | Redwood Institute, RWI       | Groningen |
| gen-4758             | BFU IP ENS001A 100 Gbit/s                      | ens001a-rt01                                           | Bluefin University, BFU      | Enschede |
| gen-4759             | GFC IP MST002A 1 Gbit/s                        | mst002a-rt08                                           | Greenfield College, GFC      | Maastricht |
| gen-4760             | BFH SP UNTAGGED RMD001A 10 Gbit/s              | rmd001a-rt07                                           | Bluefin Hospital, BFH        | Roermond |
| gen-4768             | RWL LP ENS002A-RTD002A 10 Gbit/s               | rtd002a-rt06, ens002a-rt02                             | Redwood Libraries, RWL       | Rotterdam, Enschede |
| gen-4770             | NWR IP GRQ001A 10 Gbit/s                       | grq001a-rt04                                           | Northwind Research, NWR      | Groningen |
| gen-4772             | RWL LP AMS001A-GRQ001A 10 Gbit/s               | grq001a-rt10, ams001a-rt03                             | Redwood Libraries, RWL       | Groningen, Amsterdam |
| gen-4773             | GFO L2VPN ALM001A-AMS002A-EHV002A 1 Gbit/s     | alm001a-rt12, gor002a-rt04, ams002a-rt07, ehv002a-rt01 | Greenfield Observatory, GFO  | Almere, Gorinchem, Amsterdam, Eindhoven |
| gen-4774             | RWI IP MST001A 100 Gbit/s                      | mst001a-rt11                                           | Redwood Institute, RWI       | Maastricht |
| gen-4776             | GFO L2VPN ALM002A-EHV002A 10 Gbit/s            | alm002a-rt02, ehv002a-rt06                             | Greenfield Observatory, GFO  | Almere, Eindhoven |
| gen-4779             | BFH L2VPN ALM001A-ALM002A 1 Gbit/s             | alm002a-rt04, alm001a-rt08                             | Bluefin Hospital, BFH        | Almere |
| gen-4786             | GFO IP GOR002A 100 Gbit/s                      | gor002a-rt03                                           | Greenfield Observatory, GFO  | Gorinchem |
| gen-4788             | SLM IP AMS002A 1 Gbit/s                        | ams002a-rt10                                           | Silverline Museum, SLM       | Amsterdam |
| gen-4790             | RWL SP TAGGED GRQ002A 1 Gbit/s                 | grq002a-rt10                                           | Redwood Libraries, RWL       | Groningen |
| gen-4791             | BFH SP UNTAGGED ASV001A 10 Gbit/s              | asv001a-rt05                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4795             | RWL LP GOR002A-RMD002A 10 Gbit/s               | rmd002a-rt03, gor002a-rt06                             | Redwood Libraries, RWL       | Roermond, Gorinchem |
| gen-4796             | BFH L2VPN ASV002A-RTD001A-UTR002A 10 Gbit/s    | asv002a-rt03, rtd001a-rt06, utr002a-rt07               | Bluefin Hospital, BFH        | Amstelveen, Rotterdam, Utrecht |
| gen-4797             | BFH LP MST001A-RMD001A 1 Gbit/s                | rmd001a-rt11, mst001a-rt11                             | Bluefin Hospital, BFH        | Roermond, Maastricht |
| gen-4798             | NWR SP UNTAGGED RMD002A 100 Gbit/s             | rmd002a-rt01                                           | Northwind Research, NWR      | Roermond |
| gen-4801             | NWR IP ASV001A 100 Gbit/s                      | asv001a-rt11                                           | Northwind Research, NWR      | Amstelveen |
| gen-4803             | GFO SP UNTAGGED ASV001A 1 Gbit/s               | asv001a-rt12                                           | Greenfield Observatory, GFO  | Amstelveen |
| gen-4804             | NWR L2VPN ASV001A-ENS002A 1 Gbit/s             | ens002a-rt09, asv001a-rt04                             | Northwind Research, NWR      | Enschede, Amstelveen |
| gen-4805             | RWL LP ALM002A-UTR001A 10 Gbit/s               | utr001a-rt12, alm002a-rt04                             | Redwood Libraries, RWL       | Utrecht, Almere |
| gen-4807             | GFC SP UNTAGGED EHV001A 100 Gbit/s             | ehv001a-rt06                                           | Greenfield College, GFC      | Eindhoven |
| gen-4809             | RWI LP AMS002A-MST001A 100 Gbit/s              | ams002a-rt02, mst001a-rt02                             | Redwood Institute, RWI       | Amsterdam, Maastricht |
| gen-4813             | BFU SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt07                                           | Bluefin University, BFU      | Gorinchem |
| gen-4814             | NWL L2VPN ENS002A-RMD002A 100 Gbit/s           | ens002a-rt05, rmd002a-rt05                             | Northwind Labs, NWL          | Enschede, Roermond |
| gen-4816             | RWI LP EHV001A-ENS002A 1 Gbit/s                | ehv001a-rt09, ens002a-rt03                             | Redwood Institute, RWI       | Eindhoven, Enschede |
| gen-4825             | BFH IP RMD002A 10 Gbit/s                       | rmd002a-rt07                                           | Bluefin Hospital, BFH        | Roermond |
| gen-4826             | GFC IP MST002A 1 Gbit/s                        | mst002a-rt06                                           | Greenfield College, GFC      | Maastricht |
| gen-4827             | GFO IP ALM001A 1 Gbit/s                        | alm001a-rt01                                           | Greenfield Observatory, GFO  | Almere |
| gen-4828             | BFH LP RTD002A-UTR002A 100 Gbit/s              | rtd002a-rt12, utr002a-rt12                             | Bluefin Hospital, BFH        | Rotterdam, Utrecht |
| gen-4829             | NWL SP TAGGED MST002A 100 Gbit/s               | mst002a-rt04                                           | Northwind Labs, NWL          | Maastricht |
| gen-4831             | GFO SP TAGGED RTD002A 10 Gbit/s                | rtd002a-rt02                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-4834             | RWI L2VPN ALM001A-ENS001A-RMD002A 1 Gbit/s     | rmd002a-rt03, ens001a-rt06, alm001a-rt09               | Redwood Institute, RWI       | Roermond, Enschede, Almere |
| gen-4836             | GFC SP UNTAGGED ASV002A 100 Gbit/s             | asv002a-rt12                                           | Greenfield College, GFC      | Amstelveen |
| gen-4841             | GFC L2VPN ALM001A-ARN001A-ASV001A 10 Gbit/s    | asv001a-rt02, alm001a-rt10, arn001a-rt05               | Greenfield College, GFC      | Amstelveen, Almere, Arnhem |
| gen-4844             | BFU IP EHV002A 10 Gbit/s                       | ehv002a-rt06                                           | Bluefin University, BFU      | Eindhoven |
| gen-4846             | SLA SP UNTAGGED ALM002A 1 Gbit/s               | alm002a-rt04                                           | Silverline Archives, SLA     | Almere |
| gen-4849             | BFU LP ALM001A-ASV002A 1 Gbit/s                | alm001a-rt01, asv002a-rt11                             | Bluefin University, BFU      | Almere, Amstelveen |
| gen-4851             | GFO IP ENS001A 100 Gbit/s                      | ens001a-rt02                                           | Greenfield Observatory, GFO  | Enschede |
| gen-4854             | GFO L2VPN ARN002A-ASV002A-MST001A 100 Gbit/s   | rmd002a-rt04, asv002a-rt02, arn002a-rt01, mst001a-rt03 | Greenfield Observatory, GFO  | Roermond, Amstelveen, Arnhem, Maastricht |
| gen-4856             | BFH IP RTD002A 100 Gbit/s                      | rtd002a-rt01                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4858             | GFC L2VPN ALM001A-GRQ002A 100 Gbit/s           | grq002a-rt11, alm001a-rt04                             | Greenfield College, GFC      | Groningen, Almere |
| gen-4863             | BFU LP ALM002A-GRQ001A 1 Gbit/s                | grq001a-rt04, alm002a-rt06                             | Bluefin University, BFU      | Groningen, Almere |
| gen-4865             | GFC LP GRQ002A-RMD002A 10 Gbit/s               | grq002a-rt11, rmd002a-rt07                             | Greenfield College, GFC      | Groningen, Roermond |
| gen-4866             | RWL SP TAGGED EHV002A 1 Gbit/s                 | ehv002a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-4868             | BFU SP TAGGED GOR001A 100 Gbit/s               | gor001a-rt05                                           | Bluefin University, BFU      | Gorinchem |
| gen-4869             | GFC SP TAGGED AMS002A 1 Gbit/s                 | ams002a-rt09                                           | Greenfield College, GFC      | Amsterdam |
| gen-4874             | NWR L2VPN GRQ001A-MST002A-RMD002A 100 Gbit/s   | rmd002a-rt10, grq001a-rt04, rmd002a-rt03, mst002a-rt11 | Northwind Research, NWR      | Roermond, Groningen, Maastricht |
| gen-4878             | GFC SP UNTAGGED MST001A 100 Gbit/s             | mst001a-rt09                                           | Greenfield College, GFC      | Maastricht |
| gen-4881             | GFC LP AMS002A-ARN002A 10 Gbit/s               | arn002a-rt09, ams002a-rt09                             | Greenfield College, GFC      | Arnhem, Amsterdam |
| gen-4882             | GFC LP AMS001A-ARN002A 1 Gbit/s                | ams001a-rt03, arn002a-rt12                             | Greenfield College, GFC      | Amsterdam, Arnhem |
| gen-4883             | BFH LP ALM002A-GOR001A 1 Gbit/s                | alm002a-rt01, gor001a-rt06                             | Bluefin Hospital, BFH        | Almere, Gorinchem |
| gen-4884             | RWI L2VPN GRQ002A-RTD002A 100 Gbit/s           | grq002a-rt03, rtd002a-rt11                             | Redwood Institute, RWI       | Groningen, Rotterdam |
| gen-4885             | GFO LP GRQ002A-RMD002A 1 Gbit/s                | rmd002a-rt10, grq002a-rt03                             | Greenfield Observatory, GFO  | Roermond, Groningen |
| gen-4886             | BFU SP UNTAGGED MST001A 10 Gbit/s              | mst001a-rt10                                           | Bluefin University, BFU      | Maastricht |
| gen-4894             | SLA SP TAGGED UTR001A 1 Gbit/s                 | utr001a-rt07                                           | Silverline Archives, SLA     | Utrecht |
| gen-4895             | BFU SP UNTAGGED ASV001A 100 Gbit/s             | asv001a-rt12                                           | Bluefin University, BFU      | Amstelveen |
| gen-4896             | NWR L2VPN EHV002A-ENS001A 10 Gbit/s            | ehv002a-rt08, ens001a-rt09                             | Northwind Research, NWR      | Eindhoven, Enschede |
| gen-4901             | NWL LP GOR002A-GRQ002A 1 Gbit/s                | gor002a-rt01, grq002a-rt12                             | Northwind Labs, NWL          | Gorinchem, Groningen |
| gen-4902             | NWR IP ARN002A 1 Gbit/s                        | arn002a-rt10                                           | Northwind Research, NWR      | Arnhem |
| gen-4903             | GFC L2VPN ALM002A-EHV001A 10 Gbit/s            | alm002a-rt09, ehv001a-rt04                             | Greenfield College, GFC      | Almere, Eindhoven |
| gen-4906             | RWL IP EHV001A 100 Gbit/s                      | ehv001a-rt07                                           | Redwood Libraries, RWL       | Eindhoven |
| gen-4907             | NWR IP GRQ001A 100 Gbit/s                      | grq001a-rt02                                           | Northwind Research, NWR      | Groningen |
| gen-4909             | BFH SP TAGGED EHV001A 1 Gbit/s                 | ehv001a-rt06                                           | Bluefin Hospital, BFH        | Eindhoven |
| gen-4911             | BFH SP TAGGED GOR002A 100 Gbit/s               | gor002a-rt06                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-4913             | BFH L2VPN GRQ001A-RMD002A 100 Gbit/s           | grq001a-rt11, rmd002a-rt07                             | Bluefin Hospital, BFH        | Groningen, Roermond |
| gen-4919             | BFH SP TAGGED MST002A 10 Gbit/s                | mst002a-rt07                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-4920             | BFH IP GOR001A 1 Gbit/s                        | gor001a-rt07                                           | Bluefin Hospital, BFH        | Gorinchem |
| gen-4924             | GFC SP UNTAGGED ARN002A 10 Gbit/s              | arn002a-rt11                                           | Greenfield College, GFC      | Arnhem |
| gen-4927             | BFH IP GRQ001A 10 Gbit/s                       | grq001a-rt04                                           | Bluefin Hospital, BFH        | Groningen |
| gen-4930             | BFH IP RTD002A 100 Gbit/s                      | rtd002a-rt02                                           | Bluefin Hospital, BFH        | Rotterdam |
| gen-4933             | RWI SP TAGGED ALM001A 1 Gbit/s                 | alm001a-rt01                                           | Redwood Institute, RWI       | Almere |
| gen-4936             | RWI L2VPN ALM001A-AMS002A-ENS002A 10 Gbit/s    | alm001a-rt11, ens002a-rt11, ams002a-rt10, mst001a-rt11 | Redwood Institute, RWI       | Almere, Enschede, Amsterdam, Maastricht |
| gen-4937             | GFO SP TAGGED MST002A 1 Gbit/s                 | mst002a-rt12                                           | Greenfield Observatory, GFO  | Maastricht |
| gen-4938             | RWL SP UNTAGGED ENS002A 100 Gbit/s             | ens002a-rt01                                           | Redwood Libraries, RWL       | Enschede |
| gen-4939             | RWL IP RMD002A 100 Gbit/s                      | rmd002a-rt01                                           | Redwood Libraries, RWL       | Roermond |
| gen-4943             | BFU SP TAGGED GOR002A 10 Gbit/s                | gor002a-rt09                                           | Bluefin University, BFU      | Gorinchem |
| gen-4944             | BFH L2VPN ALM002A-ASV001A-UTR002A 100 Gbit/s   | utr002a-rt12, alm002a-rt12, asv001a-rt09               | Bluefin Hospital, BFH        | Utrecht, Almere, Amstelveen |
| gen-4945             | RWI L2VPN ENS002A-GRQ001A-MST001A 1 Gbit/s     | ens002a-rt03, grq001a-rt02, ens002a-rt12, mst001a-rt09 | Redwood Institute, RWI       | Enschede, Groningen, Maastricht |
| gen-4946             | GFC L2VPN ARN001A-EHV001A-ENS001A 100 Gbit/s   | ens001a-rt06, ehv001a-rt04, ens001a-rt05, arn001a-rt06 | Greenfield College, GFC      | Enschede, Eindhoven, Arnhem |
| gen-4947             | NWL IP RMD002A 100 Gbit/s                      | rmd002a-rt10                                           | Northwind Labs, NWL          | Roermond |
| gen-4949             | BFU LP ARN002A-ASV002A 1 Gbit/s                | arn002a-rt01, asv002a-rt05                             | Bluefin University, BFU      | Arnhem, Amstelveen |
| gen-4950             | NWR L2VPN GRQ001A-MST001A 1 Gbit/s             | mst001a-rt08, grq001a-rt06                             | Northwind Research, NWR      | Maastricht, Groningen |
| gen-4952             | RWL LP ARN001A-GOR001A 100 Gbit/s              | arn001a-rt04, gor001a-rt10                             | Redwood Libraries, RWL       | Arnhem, Gorinchem |
| gen-4954             | GFO L2VPN ALM002A-EHV001A-RTD001A 10 Gbit/s    | utr001a-rt01, alm002a-rt06, rtd001a-rt08, ehv001a-rt12 | Greenfield Observatory, GFO  | Utrecht, Almere, Rotterdam, Eindhoven |
| gen-4956             | GFO LP MST002A-RTD001A 10 Gbit/s               | mst002a-rt11, rtd001a-rt04                             | Greenfield Observatory, GFO  | Maastricht, Rotterdam |
| gen-4958             | BFU IP GOR002A 1 Gbit/s                        | gor002a-rt10                                           | Bluefin University, BFU      | Gorinchem |
| gen-4960             | NWR SP TAGGED ARN001A 10 Gbit/s                | arn001a-rt07                                           | Northwind Research, NWR      | Arnhem |
| gen-4961             | BFU IP ALM001A 1 Gbit/s                        | alm001a-rt05                                           | Bluefin University, BFU      | Almere |
| gen-4963             | NWR IP GOR001A 10 Gbit/s                       | gor001a-rt01                                           | Northwind Research, NWR      | Gorinchem |
| gen-4968             | RWI L2VPN ALM002A-AMS002A-ENS001A 10 Gbit/s    | ens001a-rt01, alm002a-rt12, ams002a-rt04, grq001a-rt04 | Redwood Institute, RWI       | Enschede, Almere, Amsterdam, Groningen |
| gen-4969             | GFO SP TAGGED ENS002A 10 Gbit/s                | ens002a-rt10                                           | Greenfield Observatory, GFO  | Enschede |
| gen-4973             | RWL IP MST001A 1 Gbit/s                        | mst001a-rt09                                           | Redwood Libraries, RWL       | Maastricht |
| gen-4974             | BFH IP ASV002A 1 Gbit/s                        | asv002a-rt02                                           | Bluefin Hospital, BFH        | Amstelveen |
| gen-4977             | SLA LP ALM001A-GOR002A 10 Gbit/s               | gor002a-rt01, alm001a-rt03                             | Silverline Archives, SLA     | Gorinchem, Almere |
| gen-4978             | RWI SP UNTAGGED ENS002A 10 Gbit/s              | ens002a-rt10                                           | Redwood Institute, RWI       | Enschede |
| gen-4979             | NWL SP UNTAGGED EHV001A 1 Gbit/s               | ehv001a-rt08                                           | Northwind Labs, NWL          | Eindhoven |
| gen-4983             | NWL SP UNTAGGED MST002A 10 Gbit/s              | mst002a-rt11                                           | Northwind Labs, NWL          | Maastricht |
| gen-4984             | SLA SP UNTAGGED GOR002A 100 Gbit/s             | gor002a-rt08                                           | Silverline Archives, SLA     | Gorinchem |
| gen-4989             | SLM L2VPN ARN001A-UTR001A 100 Gbit/s           | utr001a-rt03, arn001a-rt08                             | Silverline Museum, SLM       | Utrecht, Arnhem |
| gen-4990             | RWI SP UNTAGGED ALM001A 1 Gbit/s               | alm001a-rt10                                           | Redwood Institute, RWI       | Almere |
| gen-4991             | RWL SP UNTAGGED GOR001A 100 Gbit/s             | gor001a-rt04                                           | Redwood Libraries, RWL       | Gorinchem |
| gen-4992             | RWI SP UNTAGGED EHV001A 100 Gbit/s             | ehv001a-rt09                                           | Redwood Institute, RWI       | Eindhoven |
| gen-4995             | BFU IP ARN001A 100 Gbit/s                      | arn001a-rt12                                           | Bluefin University, BFU      | Arnhem |
| gen-4996             | GFO LP ARN002A-RTD002A 100 Gbit/s              | arn002a-rt06, rtd002a-rt07                             | Greenfield Observatory, GFO  | Arnhem, Rotterdam |
| gen-4997             | GFC SP TAGGED ASV002A 1 Gbit/s                 | asv002a-rt06                                           | Greenfield College, GFC      | Amstelveen |
| gen-4998             | NWL IP EHV001A 1 Gbit/s                        | ehv001a-rt12                                           | Northwind Labs, NWL          | Eindhoven |
| gen-5000             | NWL LP GOR001A-RMD002A 10 Gbit/s               | rmd002a-rt06, gor001a-rt04                             | Northwind Labs, NWL          | Roermond, Gorinchem |
| gen-5002             | NWR IP GRQ002A 10 Gbit/s                       | grq002a-rt08                                           | Northwind Research, NWR      | Groningen |
| gen-5003             | SLM SP UNTAGGED ARN002A 1 Gbit/s               | arn002a-rt02                                           | Silverline Museum, SLM       | Arnhem |
| gen-5005             | RWI IP RTD002A 1 Gbit/s                        | rtd002a-rt05                                           | Redwood Institute, RWI       | Rotterdam |
| gen-5009             | RWL L2VPN GRQ001A-MST001A 1 Gbit/s             | mst001a-rt02, grq001a-rt05                             | Redwood Libraries, RWL       | Maastricht, Groningen |
| gen-5015             | GFC IP GOR002A 100 Gbit/s                      | gor002a-rt08                                           | Greenfield College, GFC      | Gorinchem |
| gen-5016             | BFU LP ENS001A-RTD001A 10 Gbit/s               | ens001a-rt04, rtd001a-rt03                             | Bluefin University, BFU      | Enschede, Rotterdam |
| gen-5019             | GFC LP ENS002A-GRQ002A 1 Gbit/s                | grq002a-rt08, ens002a-rt04                             | Greenfield College, GFC      | Groningen, Enschede |
| gen-5020             | NWR SP UNTAGGED GRQ001A 100 Gbit/s             | grq001a-rt01                                           | Northwind Research, NWR      | Groningen |
| gen-5026             | GFC L2VPN AMS002A-GOR001A-RTD002A 100 Gbit/s   | gor001a-rt03, rtd002a-rt10, ams002a-rt10               | Greenfield College, GFC      | Gorinchem, Rotterdam, Amsterdam |
| gen-5029             | GFO LP ALM002A-GOR001A 10 Gbit/s               | gor001a-rt03, alm002a-rt01                             | Greenfield Observatory, GFO  | Gorinchem, Almere |
| gen-5030             | SLM SP UNTAGGED ALM002A 10 Gbit/s              | alm002a-rt07                                           | Silverline Museum, SLM       | Almere |
| gen-5031             | GFO IP EHV001A 1 Gbit/s                        | ehv001a-rt10                                           | Greenfield Observatory, GFO  | Eindhoven |
| gen-5032             | NWL LP ARN002A-GRQ002A 1 Gbit/s                | arn002a-rt02, grq002a-rt06                             | Northwind Labs, NWL          | Arnhem, Groningen |
| gen-5034             | RWI LP ENS002A-MST002A 1 Gbit/s                | ens002a-rt08, mst002a-rt11                             | Redwood Institute, RWI       | Enschede, Maastricht |
| gen-5035             | NWR SP UNTAGGED ENS002A 10 Gbit/s              | ens002a-rt04                                           | Northwind Research, NWR      | Enschede |
| gen-5037             | RWI LP MST001A-RMD002A 1 Gbit/s                | mst001a-rt04, rmd002a-rt10                             | Redwood Institute, RWI       | Maastricht, Roermond |
| gen-5039             | RWL SP TAGGED ALM001A 100 Gbit/s               | alm001a-rt05                                           | Redwood Libraries, RWL       | Almere |
| gen-5043             | BFH SP TAGGED ARN002A 1 Gbit/s                 | arn002a-rt08                                           | Bluefin Hospital, BFH        | Arnhem |
| gen-5044             | NWL IP MST002A 1 Gbit/s                        | mst002a-rt04                                           | Northwind Labs, NWL          | Maastricht |
| gen-5046             | SLA LP MST001A-UTR002A 100 Gbit/s              | mst001a-rt10, utr002a-rt04                             | Silverline Archives, SLA     | Maastricht, Utrecht |
| gen-5047             | GFC L2VPN ARN002A-EHV001A-MST002A 100 Gbit/s   | arn002a-rt04, rtd002a-rt09, mst002a-rt09, ehv001a-rt10 | Greenfield College, GFC      | Arnhem, Rotterdam, Maastricht, Eindhoven |
| gen-5050             | BFU SP UNTAGGED UTR001A 1 Gbit/s               | utr001a-rt04                                           | Bluefin University, BFU      | Utrecht |
| gen-5052             | GFC LP ALM002A-RTD001A 10 Gbit/s               | rtd001a-rt08, alm002a-rt12                             | Greenfield College, GFC      | Rotterdam, Almere |
| gen-5053             | GFC L2VPN ARN002A-MST001A 100 Gbit/s           | mst001a-rt08, arn002a-rt01                             | Greenfield College, GFC      | Maastricht, Arnhem |
| gen-5054             | RWL LP EHV002A-GRQ001A 1 Gbit/s                | grq001a-rt08, ehv002a-rt07                             | Redwood Libraries, RWL       | Groningen, Eindhoven |
| gen-5056             | RWL IP ALM002A 10 Gbit/s                       | alm002a-rt09                                           | Redwood Libraries, RWL       | Almere |
| gen-5059             | BFU IP RMD002A 100 Gbit/s                      | rmd002a-rt02                                           | Bluefin University, BFU      | Roermond |
| gen-5061             | SLA SP UNTAGGED ALM001A 10 Gbit/s              | alm001a-rt08                                           | Silverline Archives, SLA     | Almere |
| gen-5064             | NWL IP GOR002A 1 Gbit/s                        | gor002a-rt03                                           | Northwind Labs, NWL          | Gorinchem |
| gen-5065             | RWL SP UNTAGGED GRQ002A 1 Gbit/s               | grq002a-rt05                                           | Redwood Libraries, RWL       | Groningen |
| gen-5066             | BFU SP UNTAGGED GOR002A 10 Gbit/s              | gor002a-rt07                                           | Bluefin University, BFU      | Gorinchem |
| gen-5068             | RWI LP RTD002A-UTR002A 100 Gbit/s              | utr002a-rt10, rtd002a-rt01                             | Redwood Institute, RWI       | Utrecht, Rotterdam |
| gen-5069             | NWL IP EHV001A 1 Gbit/s                        | ehv001a-rt11                                           | Northwind Labs, NWL          | Eindhoven |
| gen-5070             | RWI SP UNTAGGED AMS001A 1 Gbit/s               | ams001a-rt05                                           | Redwood Institute, RWI       | Amsterdam |
| gen-5071             | BFU LP ENS002A-RTD001A 100 Gbit/s              | ens002a-rt07, rtd001a-rt11                             | Bluefin University, BFU      | Enschede, Rotterdam |
| gen-5073             | NWR LP ENS002A-GRQ001A 1 Gbit/s                | grq001a-rt02, ens002a-rt08                             | Northwind Research, NWR      | Groningen, Enschede |
| gen-5074             | BFH SP UNTAGGED GRQ002A 10 Gbit/s              | grq002a-rt09                                           | Bluefin Hospital, BFH        | Groningen |
| gen-5078             | GFC L2VPN ALM002A-ENS001A 100 Gbit/s           | ens001a-rt09, alm002a-rt03                             | Greenfield College, GFC      | Enschede, Almere |
| gen-5081             | NWR LP RMD001A-RMD002A 100 Gbit/s              | rmd001a-rt05, rmd002a-rt04                             | Northwind Research, NWR      | Roermond |
| gen-5082             | RWI IP RMD001A 1 Gbit/s                        | rmd001a-rt09                                           | Redwood Institute, RWI       | Roermond |
| gen-5083             | NWR L2VPN EHV002A-MST002A-RMD001A 1 Gbit/s     | ehv002a-rt10, mst002a-rt10, rmd001a-rt08, rmd002a-rt06 | Northwind Research, NWR      | Eindhoven, Maastricht, Roermond |
| gen-5086             | BFH SP TAGGED ALM002A 10 Gbit/s                | alm002a-rt04                                           | Bluefin Hospital, BFH        | Almere |
| gen-5090             | RWI SP TAGGED GRQ001A 1 Gbit/s                 | grq001a-rt07                                           | Redwood Institute, RWI       | Groningen |
| gen-5091             | RWI LP ARN002A-EHV001A 10 Gbit/s               | ehv001a-rt12, arn002a-rt06                             | Redwood Institute, RWI       | Eindhoven, Arnhem |
| gen-5092             | GFO SP TAGGED GRQ002A 1 Gbit/s                 | grq002a-rt07                                           | Greenfield Observatory, GFO  | Groningen |
| gen-5093             | GFO L2VPN ARN001A-ENS002A-RMD002A 10 Gbit/s    | ens002a-rt05, arn001a-rt09, rmd002a-rt12, rtd001a-rt02 | Greenfield Observatory, GFO  | Enschede, Arnhem, Roermond, Rotterdam |
| gen-5095             | SLA IP ASV001A 10 Gbit/s                       | asv001a-rt04                                           | Silverline Archives, SLA     | Amstelveen |
| gen-5096             | RWL SP TAGGED ARN001A 1 Gbit/s                 | arn001a-rt12                                           | Redwood Libraries, RWL       | Arnhem |
| gen-5097             | RWL IP ARN001A 10 Gbit/s                       | arn001a-rt08                                           | Redwood Libraries, RWL       | Arnhem |
| gen-5100             | BFH SP UNTAGGED UTR001A 1 Gbit/s               | utr001a-rt05                                           | Bluefin Hospital, BFH        | Utrecht |
| gen-5101             | RWL LP EHV001A-MST002A 1 Gbit/s                | mst002a-rt01, ehv001a-rt04                             | Redwood Libraries, RWL       | Maastricht, Eindhoven |
| gen-5102             | GFO IP RTD002A 10 Gbit/s                       | rtd002a-rt07                                           | Greenfield Observatory, GFO  | Rotterdam |
| gen-5104             | GFO LP RMD002A-RMD002A 10 Gbit/s               | rmd002a-rt04, rmd002a-rt08                             | Greenfield Observatory, GFO  | Roermond |
| gen-5105             | GFC LP AMS002A-ENS001A 1 Gbit/s                | ams002a-rt06, ens001a-rt06                             | Greenfield College, GFC      | Amsterdam, Enschede |
| gen-5107             | NWR LP EHV002A-GRQ001A 100 Gbit/s              | grq001a-rt01, ehv002a-rt11                             | Northwind Research, NWR      | Groningen, Eindhoven |
| gen-5109             | BFH SP UNTAGGED MST002A 1 Gbit/s               | mst002a-rt02                                           | Bluefin Hospital, BFH        | Maastricht |
| gen-5110             | NWR LP ASV001A-RMD002A 10 Gbit/s               | asv001a-rt08, rmd002a-rt05                             | Northwind Research, NWR      | Amstelveen, Roermond |
| gen-5113             | GFC IP ARN002A 1 Gbit/s                        | arn002a-rt11                                           | Greenfield College, GFC      | Arnhem |
| gen-5114             | SLA IP GRQ001A 100 Gbit/s                      | grq001a-rt08                                           | Silverline Archives, SLA     | Groningen |
| gen-5115             | NWL L2VPN ARN002A-ASV001A-GOR001A 100 Gbit/s   | asv001a-rt11, arn002a-rt08, gor001a-rt01, mst001a-rt06 | Northwind Labs, NWL          | Amstelveen, Arnhem, Gorinchem, Maastricht |
| gen-5122             | RWI SP UNTAGGED ENS002A 1 Gbit/s               | ens002a-rt09                                           | Redwood Institute, RWI       | Enschede |
| gen-5125             | SLA IP MST001A 10 Gbit/s                       | mst001a-rt02                                           | Silverline Archives, SLA     | Maastricht |
| gen-5126             | RWI L2VPN ALM001A-MST002A-UTR001A 10 Gbit/s    | mst002a-rt02, alm001a-rt01, utr001a-rt05               | Redwood Institute, RWI       | Maastricht, Almere, Utrecht |
| gen-5129             | BFU LP ALM002A-RTD001A 100 Gbit/s              | rtd001a-rt11, alm002a-rt03                             | Bluefin University, BFU      | Rotterdam, Almere |
| gen-5132             | RWI IP GRQ002A 100 Gbit/s                      | grq002a-rt05                                           | Redwood Institute, RWI       | Groningen |
