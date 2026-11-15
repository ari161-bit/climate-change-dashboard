# EarthScape: climate analysis in R (open in RStudio)
# Uses the same real datasets as the web app. Base R only, no packages needed.
#   setwd("C:/amfahh/climatechanges")   # project folder
#   source("analysis/climate_analysis.R")

temp <- read.csv("data/Temperature.csv", check.names = FALSE, na.strings = "", stringsAsFactors = FALSE)
year_cols <- grep("^[0-9]{4}$", names(temp), value = TRUE)

# ---- Global temperature change (World row) -------------------------------------
world <- data.frame(year = as.integer(year_cols),
                    anomaly = as.numeric(unlist(temp[temp$Country == "World", year_cols])))
world <- na.omit(world)

fit <- lm(anomaly ~ year, data = world)
cat(sprintf("Warming rate: %.3f degC per decade (R^2 = %.3f)\n",
            coef(fit)["year"] * 10, summary(fit)$r.squared))

# Hold-out test like the web app: train without the last 10 years
train <- head(world, -10); test <- tail(world, 10)
m <- lm(anomaly ~ poly(year, 2, raw = TRUE), data = train)
pred <- predict(m, test)
cat(sprintf("Quadratic model on held-out years: RMSE = %.3f, MAE = %.3f\n",
            sqrt(mean((pred - test$anomaly)^2)), mean(abs(pred - test$anomaly))))

plot(world$year, world$anomaly, type = "l", col = "darkgreen", lwd = 2,
     xlab = "Year", ylab = "degC vs 1951-1980", main = "Global temperature change (FAO)")
abline(fit, col = "red", lty = 2)

# ---- Regional warming rates ------------------------------------------------------
regions <- c("Africa", "Americas", "Asia", "Europe", "Oceania")
rates <- sapply(regions, function(r) {
  v <- as.numeric(unlist(temp[temp$Country == r, year_cols]))
  coef(lm(v ~ as.integer(year_cols)))[2] * 10
})
print(round(sort(rates, decreasing = TRUE), 3))
barplot(sort(rates, decreasing = TRUE), col = "seagreen", main = "Warming per decade by region", ylab = "degC / decade")

# ---- Temperature vs climate disasters --------------------------------------------
dis <- read.csv("data/Disaster.csv", check.names = FALSE, na.strings = "", stringsAsFactors = FALSE,
                fileEncoding = "UTF-8-BOM")
dis <- dis[grepl("Number of Disasters: TOTAL$", dis$Indicator) & !is.na(dis$ISO2) & dis$ISO2 != "", ]
dyears <- grep("^[0-9]{4}$", names(dis), value = TRUE)
per_year <- data.frame(year = as.integer(dyears), disasters = colSums(sapply(dis[, dyears], as.numeric), na.rm = TRUE))
both <- merge(world, per_year, by = "year")
print(cor.test(both$anomaly, both$disasters))
plot(both$anomaly, both$disasters, pch = 19, col = "darkgreen",
     xlab = "Global temperature change (degC)", ylab = "Climate disasters", main = "Temperature vs disasters")
