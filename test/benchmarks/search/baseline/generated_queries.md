# Search benchmark generated queries

The `network_services` profile with random seed 2000: 3011 entities.

Update with `pytest test/unit_tests/benchmarks/search --inline-snapshot=fix`.

The queries `perturb.py` makes from the corpus, with the entities they expect. Only the first 10 expected
keys are shown; `count` is all of them.

| category         | query                                            | count | expected |
| ---------------- | ------------------------------------------------ | ----: | --- |
| exact            | `GFC IP GOR002A 1 Gbit/s`                        |     2 | gen-225, gen-823 |
| exact            | `SLM L2VPN AMS002A-GOR001A-GOR002A 100 Gbit/s`   |     1 | gen-2100 |
| exact            | `GFC SP UNTAGGED ALM001A 10 Gbit/s`              |     1 | gen-137 |
| exact            | `BFU SP UNTAGGED MST001A 100 Gbit/s`             |     2 | gen-4025, gen-4145 |
| exact            | `BFH SP TAGGED ARN002A 1 Gbit/s`                 |     2 | gen-2148, gen-5043 |
| exact            | `SLM LP GRQ001A-MST002A 100 Gbit/s`              |     1 | gen-4504 |
| exact            | `SLA SP TAGGED AMS002A 100 Gbit/s`               |     1 | gen-27 |
| exact            | `GFC SP UNTAGGED UTR001A 1 Gbit/s`               |     1 | gen-4526 |
| exact            | `RWL LP ARN002A-UTR001A 1 Gbit/s`                |     1 | gen-3572 |
| exact            | `GFO IP GRQ001A 1 Gbit/s`                        |     2 | gen-3244, gen-3621 |
| exact            | `GFC LP AMS001A-ASV001A 100 Gbit/s`              |     1 | gen-674 |
| exact            | `RWL IP UTR002A 10 Gbit/s`                       |     3 | gen-2693, gen-3165, gen-4275 |
| exact            | `BFH SP UNTAGGED ALM002A 1 Gbit/s`               |     1 | gen-1035 |
| exact            | `GFC L2VPN ARN002A-MST001A 100 Gbit/s`           |     1 | gen-5053 |
| exact            | `BFU SP TAGGED ARN001A 10 Gbit/s`                |     1 | gen-1000 |
| exact            | `GFO SP TAGGED MST002A 10 Gbit/s`                |     1 | gen-1161 |
| exact            | `BFH IP RTD001A 1 Gbit/s`                        |     1 | gen-4065 |
| exact            | `RWI SP TAGGED AMS002A 10 Gbit/s`                |     1 | gen-306 |
| exact            | `BFU LP GOR001A-RTD001A 10 Gbit/s`               |     1 | gen-566 |
| exact            | `RWL IP GOR001A 1 Gbit/s`                        |     3 | gen-2940, gen-3521, gen-3854 |
| prefix           | `GFC IP GOR002A 1 G`                             |     2 | gen-225, gen-823 |
| prefix           | `SLM L2VPN AMS002A-GOR001A-GOR002A 1`            |     1 | gen-2100 |
| prefix           | `GFC SP UNTAGGED ALM001A `                       |     3 | gen-137, gen-1435, gen-2415 |
| prefix           | `BFU SP UNTAGGED MST001A 10`                     |     3 | gen-4025, gen-4145, gen-4886 |
| prefix           | `BFH SP TAGGED ARN002A 1`                        |     4 | gen-1236, gen-2117, gen-2148, gen-5043 |
| prefix           | `SLM LP GRQ001A-MST002A `                        |     1 | gen-4504 |
| prefix           | `SLA SP TAGGED AMS002A 1`                        |     1 | gen-27 |
| prefix           | `GFC SP UNTAGGED UTR001A`                        |     2 | gen-1862, gen-4526 |
| prefix           | `RWL LP ARN002A-UTR001`                          |     1 | gen-3572 |
| prefix           | `GFO IP GRQ001A `                                |     5 | gen-80, gen-608, gen-1681, gen-3244, gen-3621 |
| prefix           | `GFC LP AMS001A-ASV00`                           |     2 | gen-674, gen-3239 |
| prefix           | `RWL IP UTR002A 10 G`                            |     3 | gen-2693, gen-3165, gen-4275 |
| prefix           | `BFH SP UNTAGGED ALM002A 1`                      |     3 | gen-262, gen-1035, gen-1072 |
| prefix           | `GFC L2VPN ARN002A-MST001A 1`                    |     1 | gen-5053 |
| prefix           | `BFU SP TAGGED ARN001A 1`                        |     2 | gen-820, gen-1000 |
| prefix           | `GFO SP TAGGED MST002A 1`                        |     2 | gen-1161, gen-4937 |
| prefix           | `BFH IP RTD001A `                                |     4 | gen-2312, gen-4065, gen-4137, gen-4413 |
| prefix           | `RWI SP TAGGED AMS002A 1`                        |     2 | gen-306, gen-2675 |
| prefix           | `BFU LP GOR001A-RTD001A 1`                       |     1 | gen-566 |
| prefix           | `RWL IP GOR001A 1 G`                             |     3 | gen-2940, gen-3521, gen-3854 |
| customer_typo    | `Grenefield College`                             |   358 | gen-7, gen-43, gen-58, gen-85, gen-89, gen-91, gen-94, gen-116, gen-121, gen-137, … 348 more |
| customer_typo    | `Sliverline Museum`                              |   189 | rtd001a-rt01, gen-5, gen-77, gen-79, gen-82, gen-136, gen-174, gen-179, gen-183, gen-215, … 179 more |
| customer_typo    | `Greenfield Colelge`                             |   358 | gen-7, gen-43, gen-58, gen-85, gen-89, gen-91, gen-94, gen-116, gen-121, gen-137, … 348 more |
| customer_typo    | `Blueifn University`                             |   333 | ams001a-rt10, gen-14, gen-26, gen-41, gen-65, gen-81, gen-84, gen-106, gen-126, gen-143, … 323 more |
| customer_typo    | `Bluefin Hospiatl`                               |   339 | gen-3, gen-31, gen-32, gen-50, gen-68, gen-70, gen-74, gen-125, gen-127, gen-133, … 329 more |
| customer_typo    | `Silverline Musemu`                              |   189 | rtd001a-rt01, gen-5, gen-77, gen-79, gen-82, gen-136, gen-174, gen-179, gen-183, gen-215, … 179 more |
| customer_typo    | `Silverline Acrhives`                            |   212 | rmd001a-rt01, gen-17, gen-27, gen-76, gen-101, gen-105, gen-130, gen-160, gen-184, gen-197, … 202 more |
| customer_typo    | `Greenfiled College`                             |   358 | gen-7, gen-43, gen-58, gen-85, gen-89, gen-91, gen-94, gen-116, gen-121, gen-137, … 348 more |
| customer_typo    | `Redwood Lirbaries`                              |   333 | gen-1, gen-8, gen-9, gen-19, gen-21, gen-37, gen-39, gen-56, gen-73, gen-83, … 323 more |
| customer_typo    | `Greenfield Observtaory`                         |   413 | gen-2, gen-10, gen-12, gen-16, gen-22, gen-23, gen-47, gen-49, gen-80, gen-88, … 403 more |
| customer_typo    | `Greenfield Colleeg`                             |   358 | gen-7, gen-43, gen-58, gen-85, gen-89, gen-91, gen-94, gen-116, gen-121, gen-137, … 348 more |
| customer_typo    | `Redwood Librareis`                              |   333 | gen-1, gen-8, gen-9, gen-19, gen-21, gen-37, gen-39, gen-56, gen-73, gen-83, … 323 more |
| customer_typo    | `Bluefin Hospitla`                               |   339 | gen-3, gen-31, gen-32, gen-50, gen-68, gen-70, gen-74, gen-125, gen-127, gen-133, … 329 more |
| customer_typo    | `Grenefield College`                             |   358 | gen-7, gen-43, gen-58, gen-85, gen-89, gen-91, gen-94, gen-116, gen-121, gen-137, … 348 more |
| customer_typo    | `Bleufin University`                             |   333 | ams001a-rt10, gen-14, gen-26, gen-41, gen-65, gen-81, gen-84, gen-106, gen-126, gen-143, … 323 more |
| customer_typo    | `Greenfeild Observatory`                         |   413 | gen-2, gen-10, gen-12, gen-16, gen-22, gen-23, gen-47, gen-49, gen-80, gen-88, … 403 more |
| customer_typo    | `Bluefin Hosptial`                               |   339 | gen-3, gen-31, gen-32, gen-50, gen-68, gen-70, gen-74, gen-125, gen-127, gen-133, … 329 more |
| customer_typo    | `Redwood Intsitute`                              |   359 | asv001a-rt01, gen-20, gen-34, gen-38, gen-40, gen-57, gen-97, gen-112, gen-117, gen-124, … 349 more |
| customer_typo    | `Bluefin Uinversity`                             |   333 | ams001a-rt10, gen-14, gen-26, gen-41, gen-65, gen-81, gen-84, gen-106, gen-126, gen-143, … 323 more |
| customer_typo    | `Redwood Lirbaries`                              |   333 | gen-1, gen-8, gen-9, gen-19, gen-21, gen-37, gen-39, gen-56, gen-73, gen-83, … 323 more |
| reorder          | `IP Gbit/s 1 GFC GOR002A`                        |     2 | gen-225, gen-823 |
| reorder          | `Gbit/s AMS002A-GOR001A-GOR002A L2VPN 100 SLM`   |     1 | gen-2100 |
| reorder          | `SP UNTAGGED GFC Gbit/s 10 ALM001A`              |     1 | gen-137 |
| reorder          | `SP Gbit/s 100 UNTAGGED MST001A BFU`             |     2 | gen-4025, gen-4145 |
| reorder          | `BFH SP Gbit/s 1 ARN002A TAGGED`                 |     2 | gen-2148, gen-5043 |
| reorder          | `SLM LP GRQ001A-MST002A Gbit/s 100`              |     1 | gen-4504 |
| reorder          | `AMS002A TAGGED SLA Gbit/s 100 SP`               |     1 | gen-27 |
| reorder          | `UNTAGGED 1 UTR001A SP GFC Gbit/s`               |     1 | gen-4526 |
| reorder          | `1 ARN002A-UTR001A LP RWL Gbit/s`                |     1 | gen-3572 |
| reorder          | `1 GRQ001A Gbit/s IP GFO`                        |     2 | gen-3244, gen-3621 |
| reorder          | `Gbit/s 100 AMS001A-ASV001A LP GFC`              |     1 | gen-674 |
| reorder          | `Gbit/s 10 RWL IP UTR002A`                       |     3 | gen-2693, gen-3165, gen-4275 |
| reorder          | `ALM002A Gbit/s 1 BFH UNTAGGED SP`               |     1 | gen-1035 |
| reorder          | `L2VPN Gbit/s GFC ARN002A-MST001A 100`           |     1 | gen-5053 |
| reorder          | `SP BFU Gbit/s TAGGED ARN001A 10`                |     1 | gen-1000 |
| reorder          | `10 MST002A SP GFO TAGGED Gbit/s`                |     1 | gen-1161 |
| reorder          | `BFH RTD001A Gbit/s IP 1`                        |     1 | gen-4065 |
| reorder          | `AMS002A RWI Gbit/s 10 TAGGED SP`                |     1 | gen-306 |
| reorder          | `LP Gbit/s 10 BFU GOR001A-RTD001A`               |     1 | gen-566 |
| reorder          | `1 Gbit/s RWL IP GOR001A`                        |     3 | gen-2940, gen-3521, gen-3854 |
| case_punctuation | `GOR002A-RT05`                                   |    28 | gen-195, gen-225, gen-285, gen-382, gen-390, gen-548, gen-893, gen-957, gen-1551, gen-1616, … 18 more |
| case_punctuation | `gor001a rt10`                                   |    18 | gen-237, gen-361, gen-923, gen-957, gen-1056, gen-1137, gen-2100, gen-2558, gen-2715, gen-3055, … 8 more |
| case_punctuation | `ALM001A-RT08`                                   |    19 | gen-102, gen-137, gen-525, gen-1068, gen-1544, gen-1654, gen-2146, gen-2268, gen-2509, gen-3557, … 9 more |
| case_punctuation | `MST001A-RT10`                                   |    24 | gen-211, gen-264, gen-269, gen-809, gen-1019, gen-1212, gen-1238, gen-1329, gen-1386, gen-1425, … 14 more |
| case_punctuation | `ARN002A-RT10`                                   |    18 | gen-366, gen-612, gen-1125, gen-1191, gen-2148, gen-2573, gen-2770, gen-2836, gen-3049, gen-3124, … 8 more |
| case_punctuation | `mst002a rt01`                                   |    17 | gen-205, gen-555, gen-660, gen-711, gen-1116, gen-1407, gen-1884, gen-1917, gen-1952, gen-2085, … 7 more |
| case_punctuation | `AMS002A-RT12`                                   |    12 | gen-27, gen-786, gen-941, gen-1169, gen-1282, gen-2104, gen-2582, gen-2700, gen-2729, gen-2799, … 2 more |
| case_punctuation | `UTR001A-RT01`                                   |    17 | gen-351, gen-640, gen-858, gen-1111, gen-1116, gen-2021, gen-2617, gen-2923, gen-2928, gen-3056, … 7 more |
| case_punctuation | `UTR001A-RT07`                                   |    20 | gen-567, gen-658, gen-980, gen-1333, gen-1724, gen-2580, gen-2878, gen-3193, gen-3265, gen-3366, … 10 more |
| case_punctuation | `GRQ001A-RT10`                                   |    17 | gen-8, gen-135, gen-202, gen-383, gen-570, gen-1006, gen-1277, gen-2100, gen-2946, gen-3244, … 7 more |
| case_punctuation | `AMS001A-RT08`                                   |    18 | gen-7, gen-98, gen-221, gen-256, gen-674, gen-806, gen-1006, gen-1189, gen-1526, gen-2194, … 8 more |
| case_punctuation | `utr002a rt03`                                   |    17 | gen-17, gen-315, gen-374, gen-393, gen-481, gen-655, gen-779, gen-810, gen-1359, gen-2633, … 7 more |
| case_punctuation | `ALM002A-RT10`                                   |    21 | gen-140, gen-271, gen-768, gen-887, gen-914, gen-970, gen-1035, gen-1299, gen-1362, gen-1693, … 11 more |
| case_punctuation | `MST001A-RT08`                                   |    23 | gen-66, gen-264, gen-441, gen-556, gen-1008, gen-1025, gen-1232, gen-1417, gen-1518, gen-1595, … 13 more |
| case_punctuation | `arn001a rt03`                                   |    20 | gen-299, gen-820, gen-989, gen-1000, gen-1213, gen-1383, gen-2161, gen-2163, gen-2426, gen-2723, … 10 more |
| case_punctuation | `MST002A-RT03`                                   |    18 | gen-140, gen-712, gen-804, gen-1028, gen-1125, gen-1161, gen-1233, gen-1300, gen-1463, gen-1645, … 8 more |
| case_punctuation | `rtd001a rt06`                                   |    17 | gen-12, gen-150, gen-540, gen-980, gen-1711, gen-1874, gen-1938, gen-1941, gen-1943, gen-2312, … 7 more |
| case_punctuation | `AMS002A-RT04`                                   |     9 | gen-306, gen-518, gen-1616, gen-1954, gen-2079, gen-3113, gen-3483, gen-4502, gen-4968 |
| case_punctuation | `rtd001a rt02`                                   |    20 | gen-329, gen-453, gen-566, gen-611, gen-636, gen-689, gen-729, gen-859, gen-1307, gen-1406, … 10 more |
| case_punctuation | `GOR001A-RT10`                                   |    18 | gen-237, gen-361, gen-923, gen-957, gen-1056, gen-1137, gen-2100, gen-2558, gen-2715, gen-3055, … 8 more |
| identifier       | `gor002a-rt05`                                   |    28 | gen-195, gen-225, gen-285, gen-382, gen-390, gen-548, gen-893, gen-957, gen-1551, gen-1616, … 18 more |
| identifier       | `gor001a-rt10`                                   |    18 | gen-237, gen-361, gen-923, gen-957, gen-1056, gen-1137, gen-2100, gen-2558, gen-2715, gen-3055, … 8 more |
| identifier       | `alm001a-rt08`                                   |    19 | gen-102, gen-137, gen-525, gen-1068, gen-1544, gen-1654, gen-2146, gen-2268, gen-2509, gen-3557, … 9 more |
| identifier       | `mst001a-rt10`                                   |    24 | gen-211, gen-264, gen-269, gen-809, gen-1019, gen-1212, gen-1238, gen-1329, gen-1386, gen-1425, … 14 more |
| identifier       | `arn002a-rt10`                                   |    18 | gen-366, gen-612, gen-1125, gen-1191, gen-2148, gen-2573, gen-2770, gen-2836, gen-3049, gen-3124, … 8 more |
| identifier       | `mst002a-rt01`                                   |    17 | gen-205, gen-555, gen-660, gen-711, gen-1116, gen-1407, gen-1884, gen-1917, gen-1952, gen-2085, … 7 more |
| identifier       | `ams002a-rt12`                                   |    12 | gen-27, gen-786, gen-941, gen-1169, gen-1282, gen-2104, gen-2582, gen-2700, gen-2729, gen-2799, … 2 more |
| identifier       | `utr001a-rt01`                                   |    17 | gen-351, gen-640, gen-858, gen-1111, gen-1116, gen-2021, gen-2617, gen-2923, gen-2928, gen-3056, … 7 more |
| identifier       | `utr001a-rt07`                                   |    20 | gen-567, gen-658, gen-980, gen-1333, gen-1724, gen-2580, gen-2878, gen-3193, gen-3265, gen-3366, … 10 more |
| identifier       | `grq001a-rt10`                                   |    17 | gen-8, gen-135, gen-202, gen-383, gen-570, gen-1006, gen-1277, gen-2100, gen-2946, gen-3244, … 7 more |
| identifier       | `ams001a-rt08`                                   |    18 | gen-7, gen-98, gen-221, gen-256, gen-674, gen-806, gen-1006, gen-1189, gen-1526, gen-2194, … 8 more |
| identifier       | `utr002a-rt03`                                   |    17 | gen-17, gen-315, gen-374, gen-393, gen-481, gen-655, gen-779, gen-810, gen-1359, gen-2633, … 7 more |
| identifier       | `alm002a-rt10`                                   |    21 | gen-140, gen-271, gen-768, gen-887, gen-914, gen-970, gen-1035, gen-1299, gen-1362, gen-1693, … 11 more |
| identifier       | `mst001a-rt08`                                   |    23 | gen-66, gen-264, gen-441, gen-556, gen-1008, gen-1025, gen-1232, gen-1417, gen-1518, gen-1595, … 13 more |
| identifier       | `arn001a-rt03`                                   |    20 | gen-299, gen-820, gen-989, gen-1000, gen-1213, gen-1383, gen-2161, gen-2163, gen-2426, gen-2723, … 10 more |
| identifier       | `mst002a-rt03`                                   |    18 | gen-140, gen-712, gen-804, gen-1028, gen-1125, gen-1161, gen-1233, gen-1300, gen-1463, gen-1645, … 8 more |
| identifier       | `rtd001a-rt06`                                   |    17 | gen-12, gen-150, gen-540, gen-980, gen-1711, gen-1874, gen-1938, gen-1941, gen-1943, gen-2312, … 7 more |
| identifier       | `ams002a-rt04`                                   |     9 | gen-306, gen-518, gen-1616, gen-1954, gen-2079, gen-3113, gen-3483, gen-4502, gen-4968 |
| identifier       | `rtd001a-rt02`                                   |    20 | gen-329, gen-453, gen-566, gen-611, gen-636, gen-689, gen-729, gen-859, gen-1307, gen-1406, … 10 more |
| identifier       | `gor001a-rt10`                                   |    18 | gen-237, gen-361, gen-923, gen-957, gen-1056, gen-1137, gen-2100, gen-2558, gen-2715, gen-3055, … 8 more |
| multi_field      | `Greenfield College Gorinchem`                   |    50 | gen-43, gen-121, gen-195, gen-225, gen-285, gen-612, gen-732, gen-754, gen-816, gen-823, … 40 more |
| multi_field      | `Silverline Museum Gorinchem`                    |    28 | gen-244, gen-426, gen-466, gen-654, gen-688, gen-723, gen-733, gen-905, gen-923, gen-1178, … 18 more |
| multi_field      | `Greenfield College Almere`                      |    62 | gen-85, gen-137, gen-362, gen-495, gen-555, gen-705, gen-714, gen-883, gen-887, gen-964, … 52 more |
| multi_field      | `Bluefin University Maastricht`                  |    40 | gen-14, gen-84, gen-176, gen-393, gen-404, gen-441, gen-588, gen-649, gen-660, gen-678, … 30 more |
| multi_field      | `Bluefin Hospital Arnhem`                        |    43 | gen-70, gen-234, gen-283, gen-420, gen-529, gen-745, gen-761, gen-782, gen-835, gen-922, … 33 more |
| multi_field      | `Silverline Museum Maastricht`                   |    29 | gen-79, gen-244, gen-269, gen-503, gen-704, gen-884, gen-1028, gen-1033, gen-1117, gen-1162, … 19 more |
| multi_field      | `Silverline Archives Amsterdam`                  |    32 | gen-27, gen-105, gen-430, gen-518, gen-562, gen-786, gen-893, gen-1131, gen-1358, gen-1367, … 22 more |
| multi_field      | `Greenfield College Utrecht`                     |    56 | gen-121, gen-351, gen-355, gen-455, gen-520, gen-658, gen-720, gen-749, gen-810, gen-980, … 46 more |
| multi_field      | `Redwood Libraries Utrecht`                      |    40 | gen-349, gen-640, gen-844, gen-858, gen-1116, gen-1135, gen-1370, gen-1408, gen-1848, gen-1856, … 30 more |
| multi_field      | `Greenfield Observatory Groningen`               |    54 | gen-16, gen-23, gen-49, gen-80, gen-88, gen-150, gen-202, gen-275, gen-378, gen-412, … 44 more |
| multi_field      | `Greenfield College Amsterdam`                   |    50 | gen-7, gen-121, gen-257, gen-285, gen-362, gen-555, gen-674, gen-766, gen-778, gen-798, … 40 more |
| multi_field      | `Redwood Libraries Utrecht`                      |    40 | gen-349, gen-640, gen-844, gen-858, gen-1116, gen-1135, gen-1370, gen-1408, gen-1848, gen-1856, … 30 more |
| multi_field      | `Bluefin Hospital Almere`                        |    56 | gen-32, gen-70, gen-248, gen-262, gen-320, gen-556, gen-617, gen-737, gen-768, gen-800, … 46 more |
| multi_field      | `Greenfield College Maastricht`                  |    47 | gen-195, gen-555, gen-705, gen-969, gen-988, gen-1025, gen-1125, gen-1238, gen-1312, gen-1329, … 37 more |
| multi_field      | `Bluefin University Arnhem`                      |    59 | gen-14, gen-81, gen-146, gen-151, gen-187, gen-219, gen-272, gen-336, gen-341, gen-374, … 49 more |
| multi_field      | `Greenfield Observatory Maastricht`              |    46 | gen-10, gen-49, gen-93, gen-155, gen-171, gen-194, gen-211, gen-222, gen-279, gen-313, … 36 more |
| multi_field      | `Bluefin Hospital Rotterdam`                     |    45 | gen-125, gen-127, gen-234, gen-307, gen-420, gen-683, gen-708, gen-729, gen-1092, gen-1446, … 35 more |
| multi_field      | `Redwood Institute Amsterdam`                    |    47 | gen-182, gen-188, gen-221, gen-306, gen-386, gen-694, gen-713, gen-769, gen-780, gen-806, … 37 more |
| multi_field      | `Bluefin University Rotterdam`                   |    34 | gen-166, gen-566, gen-678, gen-689, gen-764, gen-819, gen-854, gen-1005, gen-1335, gen-1369, … 24 more |
| multi_field      | `Redwood Libraries Gorinchem`                    |    47 | gen-1, gen-9, gen-83, gen-177, gen-240, gen-650, gen-671, gen-752, gen-791, gen-990, … 37 more |
